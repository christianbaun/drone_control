# SPDX-License-Identifier: Apache-2.0
"""Collect and display live telemetry with optional data requests and no flight commands.

File: drone_control/telemetry.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import math
import os
import shutil
import sys
import time
from pymavlink import mavutil
from .navigation import navigation_lines
from .dashboard import dashboard
from .radio import VTX_PARAMS, radio_lines, vtx_lines


def render(cache, now=None, battery_profile=None):
    now = time.monotonic() if now is None else now

    def message(kind):
        pair = cache.get(kind)
        return pair[0] if pair and now - pair[1] <= 3 else None

    def number(value, unit, digits=2):
        if value is None or not math.isfinite(value):
            return '—'
        return f'{value:.{digits}f} {unit}'

    beat = message('HEARTBEAT')
    mode = mavutil.mode_string_v10(beat) if beat else '—'
    armed = ('ARMED' if beat.base_mode & 128 else 'DISARMED') if beat else '—'
    link = 'OK' if beat else 'KEIN FRISCHER HEARTBEAT'
    position = message('GLOBAL_POSITION_INT')
    attitude = message('ATTITUDE')
    distance = message('DISTANCE_SENSOR_DOWN')
    battery = message('SYS_STATUS')
    ekf = message('EKF_STATUS_REPORT')
    warnings = []
    if ekf:
        for bit, label in [
            (32768, 'GPS unplausibel (GPS_GLITCHING)'),
            (1024, 'Filter nicht initialisiert (UNINITIALIZED)'),
            (128, 'Konstantpositionsmodus (CONST_POS_MODE)'),
        ]:
            if ekf.flags & bit:
                warnings.append(label)
    ekf_status = ('; '.join(warnings) if warnings else 'keine Warnflags gemeldet') if ekf else '—'
    source_message = cache.get('EKF_SOURCE_SET_TEXT')
    source_labels = {'1': 'GPS / Barometer', '2': 'Optical Flow / Barometer',
                     '3': 'Optical Flow / Entfernungssensor'}
    if source_message:
        source_id = source_message[0][-1]
        age = max(0, now - source_message[1])
        source_text = f"{source_id} ({source_labels[source_id]}; Profil laut deiner Konfiguration), vor {age:.0f} s"
    else:
        source_text = 'unbekannt; RC8-Schalter umlegen, um FC-Meldung zu empfangen'
    ground = None
    if distance and distance.min_distance <= distance.current_distance <= distance.max_distance:
        # 0 = unbekannt/unbelegt, 1 = ungültig; Feld fehlt bei MAVLink 1.
        if getattr(distance, 'signal_quality', 0) != 1:
            ground = distance.current_distance / 100
    if ground is not None:
        distance_status = 'Messwert im Sensorbereich'
    elif distance:
        distance_status = ('Signal ungültig' if getattr(distance, 'signal_quality', 0) == 1
                           else f'außerhalb Messbereich {distance.min_distance / 100:.2f}–'
                                f'{distance.max_distance / 100:.2f} m; roh {distance.current_distance} cm')
    elif 'DISTANCE_SENSOR_DOWN' in cache:
        distance_status = 'Nach-unten-Messung älter als 3 s'
    elif message('DISTANCE_SENSOR'):
        distance_status = f"nur andere Orientierung empfangen: {message('DISTANCE_SENSOR').orientation}"
    else:
        distance_status = 'keine frische DISTANCE_SENSOR-Nachricht'
    voltage = battery.voltage_battery / 1000 if battery and battery.voltage_battery != 65535 else None
    current = battery.current_battery / 100 if battery and battery.current_battery != -1 else None
    remaining = battery.battery_remaining if battery and battery.battery_remaining != -1 else None
    angles = [number(math.degrees(getattr(attitude, key)), '°', 1) if attitude else '—'
              for key in ('roll', 'pitch', 'yaw')]
    speed = math.hypot(position.vx, position.vy) / 100 if position else None
    battery_text = f'Batterie: {number(voltage, "V")} | {number(current, "A")} | {number(remaining, "%", 0)}'
    if battery_profile:
        battery_text += ' | ' + battery_profile.describe(voltage)
    arming_lines = []
    for text, stamp in cache.get('ARMING_MESSAGES', [])[-3:]:
        arming_lines.append(f'Arming-Hinweis (FC, vor {max(0, now - stamp):.0f} s): {text}')
    return '\n'.join([
        'Quadcopter-Telemetrie · Strg+C beendet die Anzeige',
        f'Verbindung: {link} | Modus: {mode} | Motoren: {armed}',
        *arming_lines,
        f'Höhe relativ Home: {number(position.relative_alt / 1000 if position else None, "m")}',
        f'Bodenabstand (Sensor, entlang Messachse): {number(ground, "m")}',
        f'Abstand-Diagnose: {distance_status}',
        f'Roll: {angles[0]} | Pitch: {angles[1]} | Yaw: {angles[2]}',
        f'Geschwindigkeit horizontal: {number(speed, "m/s")} | '
        f'Steigen: {number(-position.vz / 100 if position else None, "m/s")}',
        *navigation_lines(message),
        battery_text,
        *radio_lines(message),
        *vtx_lines(cache, now),
        f'EKF Source Set (letzte FC-Umschaltmeldung): {source_text}',
        f'EKF-Status: {ekf_status}',
        '— = nicht empfangen, älter als 3 s oder ungültig',
    ])


def terminal_frame(text):
    # Jede Zeile löschen, auch wenn der neue Wert kürzer ist; CRLF vermeidet
    # Abhängigkeit von den Newline-Einstellungen des Terminals.
    return '\033[H' + '\r\n'.join('\033[2K' + line for line in text.splitlines()) + '\033[J'


def watch(vehicle, request_streams=True, battery_profile=None):
    if request_streams:
        # Ausschließlich Telemetrieraten anfragen; keine GCS-Heartbeats senden.
        # BATTERY_STATUS (147) wird von ELRS für die EdgeTX-Akkusensoren benötigt.
        for message_id, hz in [(30, 2), (33, 2), (1, 1), (147, 1), (132, 2), (193, 1), (24, 1), (26, 1), (65, 1)]:
            vehicle.send_command(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                                 message_id, 1_000_000 / hz)
            vehicle.pump()
    next_parameter = 0
    parameter_index = 0
    next_frame = 0
    terminal = sys.stdout.isatty()
    if terminal:
        print('\033[?1049h\033[?25l\033[2J\033[H', end='', flush=True)
    try:
        while True:
            vehicle.pump()
            now = time.monotonic()
            if request_streams and now >= next_parameter:
                name = VTX_PARAMS[parameter_index]
                vehicle.link.mav.param_request_read_send(vehicle.system, vehicle.component, name.encode(), -1)
                parameter_index = (parameter_index + 1) % len(VTX_PARAMS)
                next_parameter = now + (0.4 if parameter_index else 20)
            if now >= next_frame:
                if terminal:
                    size = shutil.get_terminal_size((100, 30))
                    colored = 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb'
                    text = dashboard(render(vehicle.cache, now, battery_profile), size.columns, size.lines, colored)
                    print(terminal_frame(text), end='', flush=True)
                else:
                    print(render(vehicle.cache, now, battery_profile), end='\n\n', flush=True)
                next_frame = now + (0.5 if terminal else 2)
    finally:
        if terminal:
            print("\033[0m\033[?25h\033[?1049l", end="", flush=True)
