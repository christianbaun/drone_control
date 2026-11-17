# SPDX-License-Identifier: Apache-2.0
"""Format GPS position, heading, and magnetometer telemetry with validity checks.

File: drone_control/navigation.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import math
from pymavlink import mavutil


def heading(degrees):
    if degrees is None or not math.isfinite(degrees):
        return '—'
    degrees %= 360
    directions = ('N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW')
    return f'{degrees:.1f} ° ({directions[int((degrees + 22.5) // 45) % 8]})'


def navigation_lines(message):
    gps = message('GPS_RAW_INT')
    attitude = message('ATTITUDE')
    position = message('GLOBAL_POSITION_INT')
    status = message('SYS_STATUS')
    mag = message('SCALED_IMU')
    yaw = None
    if position is not None and getattr(position, 'hdg', 65535) != 65535:
        yaw = position.hdg / 100
    elif attitude is not None:
        yaw = math.degrees(attitude.yaw)
    fix_names = {0: 'kein GPS', 1: 'kein Fix', 2: '2D', 3: '3D', 4: 'DGPS',
                 5: 'RTK Float', 6: 'RTK Fixed', 7: 'statisch', 8: 'PPP'}
    fix = fix_names.get(gps.fix_type, f'Typ {gps.fix_type}') if gps else '—'
    satellites = str(gps.satellites_visible) if gps and gps.satellites_visible != 255 else '—'
    coords = altitude = course = hdop = vdop = accuracy = '—'
    if gps:
        if gps.eph != 65535:
            hdop = f'{gps.eph / 100:.2f}'
        if gps.epv != 65535:
            vdop = f'{gps.epv / 100:.2f}'
        if gps.fix_type >= 2:
            lat, lon = gps.lat / 1e7, gps.lon / 1e7
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                coords = f'{lat:.7f}, {lon:.7f} (Breite, Länge; WGS84)'
            if gps.cog != 65535:
                course = heading(gps.cog / 100)
            # Erweiterungsfeld: 0 bedeutet nicht gesetzt/unbekannt.
            h_acc = getattr(gps, 'h_acc', 0)
            if h_acc > 0:
                accuracy = f'{h_acc / 1000:.2f} m'
        if gps.fix_type >= 3:
            altitude = f'{gps.alt / 1000:.2f} m MSL'
    compass = '—'
    if status is not None and hasattr(status, 'onboard_control_sensors_present'):
        bit = mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_MAG
        if not status.onboard_control_sensors_present & bit:
            compass = 'nicht vorhanden laut FC'
        elif not status.onboard_control_sensors_enabled & bit:
            compass = 'vorhanden, deaktiviert laut FC'
        else:
            compass = 'gesund laut FC' if status.onboard_control_sensors_health & bit else 'FEHLER laut FC'
    magnetic = '—'
    if mag is not None:
        x, y, z = mag.xmag, mag.ymag, mag.zmag
        if (x, y, z) != (0, 0, 0):
            magnetic = f'X={x}, Y={y}, Z={z} mG | Betrag={math.sqrt(x*x + y*y + z*z):.1f} mG'
    return [
        f'Ausrichtung (FC-Schätzung): {heading(yaw)}',
        f'GPS: Fix={fix} | Satelliten={satellites} | HDOP={hdop} | VDOP={vdop}',
        f'GPS-Position: {coords}',
        f'GPS-Höhe: {altitude} | horizontale Genauigkeit (Empfänger): {accuracy}',
        f'GPS-Bewegungskurs: {course} (keine Ausrichtung im Stillstand)',
        f'Magnetometer: {compass}',
        f'Magnetfeld (SCALED_IMU): {magnetic}',
    ]
