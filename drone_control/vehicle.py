# SPDX-License-Identifier: Apache-2.0
"""Manage MAVLink transport, flight checks, command acknowledgments, and RC takeover.

File: drone_control/vehicle.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import logging
import math
import re
import time
from pymavlink import mavutil
from .radio import VTX_PARAMS

LOG = logging.getLogger(__name__)
M = mavutil.mavlink
GUIDED, LAND = 4, 9


class FlightError(RuntimeError):
    pass


class CommandRejected(FlightError):
    pass


class PilotOverride(FlightError):
    pass


class Vehicle:
    def __init__(self, endpoint, baud=115200, system=1, source=255):
        self.link = mavutil.mavlink_connection(
            endpoint, baud=baud, source_system=source, source_component=190)
        self.system, self.source = system, source
        self.component = 1
        self.cache = {}
        self.last_beat = 0
        self.heartbeat_enabled = False
        self.expected_mode = None
        self.overridden = False
        self.started = False

    def close(self):
        self.heartbeat_enabled = False
        self.link.close()

    def send_command(self, command, *params):
        self.link.mav.command_long_send(self.system, self.component, command, 0,
                                       *(list(params) + [0] * (7 - len(params))))

    def pump(self):
        now = time.monotonic()
        if self.heartbeat_enabled and now - self.last_beat >= 1:
            self.link.mav.heartbeat_send(M.MAV_TYPE_GCS, M.MAV_AUTOPILOT_INVALID,
                                         0, 0, M.MAV_STATE_ACTIVE)
            self.last_beat = now
        msg = self.link.recv_match(blocking=True, timeout=0.1)
        # Funkmodule senden RADIO_STATUS oft mit eigener System-/Komponenten-ID.
        # Nur Diagnose übernehmen, niemals deren Heartbeats oder Flugzustände.
        if msg and msg.get_type() == "RADIO_STATUS" and (
                msg.get_srcSystem() == self.system or msg.get_srcComponent() == 68):
            self.cache["RADIO_STATUS"] = (msg, time.monotonic())
        if msg and msg.get_srcSystem() == self.system and msg.get_srcComponent() == self.component:
            kind = msg.get_type()
            self.cache[kind] = (msg, time.monotonic())
            if kind == "DISTANCE_SENSOR" and msg.orientation == M.MAV_SENSOR_ROTATION_PITCH_270:
                self.cache["DISTANCE_SENSOR_DOWN"] = (msg, time.monotonic())
            if kind == "PARAM_VALUE":
                name = msg.param_id.decode() if isinstance(msg.param_id, bytes) else msg.param_id
                name = name.rstrip("\x00")
                if name in VTX_PARAMS:
                    self.cache[name] = (msg, time.monotonic())
            if kind == "STATUSTEXT":
                text = msg.text.decode(errors="replace") if isinstance(msg.text, bytes) else msg.text
                if re.fullmatch(r"Using EKF Source Set [123]", text.rstrip("\x00")):
                    self.cache["EKF_SOURCE_SET_TEXT"] = (text.rstrip("\x00"), time.monotonic())
                text = text.rstrip("\x00")
                if text.lower().startswith(("prearm:", "arm:", "arming:")):
                    history = self.cache.setdefault("ARMING_MESSAGES", [])
                    history.append((text, time.monotonic()))
                    del history[:-10]
                LOG.info("FC: %s", text)
            if kind == "HEARTBEAT" and self.expected_mode is not None:
                if msg.custom_mode not in self.expected_mode:
                    self.overridden = True  # Auch bei anschließendem Zurückschalten verriegelt.
        return msg

    def fresh(self, kind, max_age=3):
        pair = self.cache.get(kind)
        if pair is None or time.monotonic() - pair[1] > max_age:
            raise FlightError(f"Keine frische Telemetrie: {kind}")
        return pair[0]

    def guard(self):
        if self.overridden:
            raise PilotOverride("Flugmodus geändert: Steuerung dauerhaft abgegeben")
        beat = self.fresh("HEARTBEAT")
        if self.expected_mode is not None and beat.custom_mode not in self.expected_mode:
            self.overridden = True
            raise PilotOverride("Pilot oder FC hat den Flugmodus gewechselt")
        if beat.system_status in (M.MAV_STATE_CRITICAL, M.MAV_STATE_EMERGENCY):
            raise FlightError("Flugcontroller meldet kritischen Zustand")

    def wait(self, predicate, timeout, guarded=True):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump()
            if guarded:
                self.guard()
            if predicate():
                return
        raise FlightError("Zeitlimit überschritten")

    def register_backpack(self, peer):
        # Gleicher UDP-Socket für Anmeldung, Empfang und spätere Antworten.
        # PING setzt beim Backpack die GCS-Ziel-IP, ohne den GCS-Failsafe
        # durch einen HEARTBEAT zu aktivieren oder einen Flugmodus zu ändern.
        self.link.clients.add(peer)
        self.link.mav.ping_send(int(time.time() * 1_000_000), 0, self.system, self.component)

    def connect(self):
        try:
            self.wait(lambda: "HEARTBEAT" in self.cache, 15, guarded=False)
        except FlightError as error:
            raise FlightError("Kein FC-Heartbeat empfangen. Drohne/ELRS-Link, Backpack → Telemetry → WiFi, "
                              "UDP-Firewall und andere Bodenstationen prüfen. Im Heimnetz ggf. --backpack nutzen.") from error
        beat = self.fresh("HEARTBEAT")
        if beat.autopilot != M.MAV_AUTOPILOT_ARDUPILOTMEGA or beat.type != M.MAV_TYPE_QUADROTOR:
            raise FlightError("Ziel ist kein ArduPilot-Quadcopter")
        LOG.info("Verbunden: System %s, Modus %s (ID %s)",
                 self.system, mavutil.mode_string_v10(beat), beat.custom_mode)

    def request_streams(self):
        # Kleine Datenraten für ELRS. ACKs dieser optionalen Anfragen nicht auswerten.
        for message_id, hz in [(33, 2), (193, 1), (245, 1), (132, 1)]:
            self.send_command(M.MAV_CMD_SET_MESSAGE_INTERVAL, message_id, 1_000_000 / hz)
            self.pump()

    def parameter(self, name):
        self.cache.pop("PARAM_VALUE", None)
        self.link.mav.param_request_read_send(self.system, self.component, name.encode(), -1)
        def received():
            pair = self.cache.get("PARAM_VALUE")
            if not pair:
                return False
            param_id = pair[0].param_id
            if isinstance(param_id, bytes):
                param_id = param_id.decode()
            return param_id.rstrip("\x00") == name
        self.wait(received, 4)
        return self.cache["PARAM_VALUE"][0].param_value

    def command(self, command, *params, timeout=8):
        self.guard()
        self.cache.pop("COMMAND_ACK", None)
        self.send_command(command, *params)
        def accepted():
            pair = self.cache.get("COMMAND_ACK")
            if not pair or pair[0].command != command:
                return False
            result = pair[0].result
            if result == M.MAV_RESULT_IN_PROGRESS:
                return False
            if result != M.MAV_RESULT_ACCEPTED:
                entry = M.enums['MAV_RESULT'].get(result)
                label = entry.name if entry else str(result)
                raise CommandRejected(f"Befehl {command} abgelehnt: {label} ({result})")
            return True
        self.wait(accepted, timeout)

    def preflight(self):
        beat = self.fresh("HEARTBEAT")
        if beat.base_mode & M.MAV_MODE_FLAG_SAFETY_ARMED:
            raise FlightError("Start nur mit disarmter Drohne")
        if beat.custom_mode != GUIDED:
            raise FlightError("Zuerst GUIDED über den RC-Modusschalter wählen")
        self.expected_mode = (GUIDED,)
        self.heartbeat_enabled = True
        self.request_streams()
        self.wait(lambda: all(k in self.cache for k in
                             ("GLOBAL_POSITION_INT", "EKF_STATUS_REPORT", "EXTENDED_SYS_STATE")), 10)
        if self.fresh("EXTENDED_SYS_STATE").landed_state != M.MAV_LANDED_STATE_ON_GROUND:
            raise FlightError("FC bestätigt keinen Bodenkontakt")
        self.check_navigation()
        # Keine Parameter schreiben. Failsafe muss bereits am FC eingerichtet sein.
        if self.parameter("FS_GCS_ENABLE") != 5:
            raise FlightError("Für dieses Projekt FS_GCS_ENABLE=5 (LAND) erforderlich")
        if not 2 <= self.parameter("FS_GCS_TIMEOUT") <= 10:
            raise FlightError("FS_GCS_TIMEOUT muss zwischen 2 und 10 Sekunden liegen")
        try:
            gcs = self.parameter("MAV_GCS_SYSID")
        except FlightError:
            self.guard()
            gcs = self.parameter("SYSID_MYGCS")
        if int(gcs) != self.source:
            raise FlightError("GCS-System-ID am FC passt nicht zu --source-system")
        self.check_arming_configuration()
        if self.parameter("FS_THR_ENABLE") == 0:
            raise FlightError("RC-Failsafe ist deaktiviert")
        speed = self.parameter("LAND_SPEED")
        if not 10 <= speed <= 30:
            raise FlightError("LAND_SPEED muss für diesen Ablauf 10–30 cm/s betragen")
        LOG.info("Vorprüfungen bestanden; LAND_SPEED=%s cm/s", speed)

    def check_navigation(self):
        if self.started and not (self.fresh("HEARTBEAT").base_mode & M.MAV_MODE_FLAG_SAFETY_ARMED):
            raise FlightError("Motoren unerwartet disarmt")
        flags = self.fresh("EKF_STATUS_REPORT").flags
        needed = 1 | 2 | 4 | 8 | 32  # attitude, horiz/vert velocity, horiz rel pos, vert abs pos
        if flags & needed != needed or flags & (128 | 32768):
            raise FlightError(f"EKF nicht bereit für Positionsflug: flags={flags}")
        position = self.fresh("GLOBAL_POSITION_INT")
        if not math.isfinite(position.relative_alt):
            raise FlightError("Ungültige relative Höhe")
        return position.relative_alt / 1000

    def check_arming_configuration(self):
        value = self.parameter("ARMING_CHECK")
        if not math.isfinite(value) or value < 0 or value != int(value):
            raise FlightError(f"Ungültige ARMING_CHECK-Bitmaske: {value}")
        mask = int(value)
        if mask == 0:
            raise FlightError("ARMING_CHECK=0 deaktiviert optionale Arming-Prüfungen vollständig; "
                              "Prüfungen am FC gezielt konfigurieren")
        if mask & 1:
            LOG.info("Arming-Prüfungen: alle am FC aktiviert (ARMING_CHECK=%s)", mask)
        else:
            LOG.warning("Individuelle Arming-Prüfungen am FC: ARMING_CHECK=%s. "
                        "Nur die dort ausgewählten Prüfungen gelten; keine Umgehung durch das Programm.", mask)

    def arm_only(self):
        """Bodentest: normal armen, keinen Start und keine GCS-Heartbeats senden."""
        beat = self.fresh("HEARTBEAT")
        if beat.base_mode & M.MAV_MODE_FLAG_SAFETY_ARMED:
            raise FlightError("Drohne ist bereits scharfgeschaltet")
        self.expected_mode = (beat.custom_mode,)
        self.check_arming_configuration()
        self.send_command(M.MAV_CMD_SET_MESSAGE_INTERVAL, M.MAVLINK_MSG_ID_EXTENDED_SYS_STATE, 1_000_000)
        self.wait(lambda: "EXTENDED_SYS_STATE" in self.cache, 8)
        if self.fresh("EXTENDED_SYS_STATE").landed_state != M.MAV_LANDED_STATE_ON_GROUND:
            raise FlightError("Armen nur bei vom FC bestätigtem Bodenkontakt")
        self.arm()
        LOG.info("Nur Armen bestätigt. Kein Startbefehl; Programm endet. Per RC wieder disarmen. "
                 "Automatisches Disarmen/Failsafes bleiben dem FC überlassen.")

    def arming_diagnostics(self, since, collect=False):
        if collect:
            # STATUSTEXT kann hinter dem negativen ACK eintreffen.
            # Nur empfangen; kein erneuter Armversuch, keine Parameteränderung.
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                self.pump()
                self.guard()
        history = self.cache.get("ARMING_MESSAGES", [])
        recent = list(dict.fromkeys(text for text, stamp in history if stamp >= since))
        if recent:
            return "FC-Begründung: " + " | ".join(recent)
        return "Keine konkrete Arm-/PreArm-Begründung vom FC empfangen; Telemetrie/FC-Meldungen prüfen."

    def arm(self):
        since = time.monotonic()
        try:
            self.command(M.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        except CommandRejected as error:
            reason = self.arming_diagnostics(since, collect=True)
            raise FlightError(f"Armen abgelehnt. {reason} [{error}]") from error
        self.started = True
        try:
            self.wait(lambda: self.fresh("HEARTBEAT").base_mode & M.MAV_MODE_FLAG_SAFETY_ARMED, 8)
        except PilotOverride:
            raise
        except FlightError as error:
            raise FlightError(f"Armed-Zustand nicht bestätigt: {error}. {self.arming_diagnostics(since)}") from error
        LOG.info("Motoren scharfgeschaltet")

    def takeoff(self, height, timeout):
        LOG.info("Start auf %.2f m relativ zu Home", height)
        self.command(M.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, height)
        stable_since = None
        def reached():
            nonlocal stable_since
            altitude = self.check_navigation()
            if altitude > height + 0.35:
                raise FlightError("Zielhöhe deutlich überschritten")
            if abs(altitude - height) <= 0.10:
                stable_since = stable_since or time.monotonic()
                return time.monotonic() - stable_since >= 1
            stable_since = None
            return False
        self.wait(reached, timeout)

    def hold(self, seconds):
        LOG.info("Position %.1f Sekunden halten", seconds)
        until = time.monotonic() + seconds
        def finished():
            self.check_navigation()
            return time.monotonic() >= until
        self.wait(finished, seconds + 2)

    def land(self, timeout):
        LOG.info("LAND anfordern; FC regelt Landung und automatisches Disarmen")
        self.guard()
        # Zielmodus vor Senden setzen: eigene LAND-Bestätigung ist keine Übernahme.
        self.expected_mode = (GUIDED, LAND)
        self.command(M.MAV_CMD_NAV_LAND)
        self.wait(lambda: self.fresh("HEARTBEAT").custom_mode == LAND, 5)
        self.expected_mode = (LAND,)
        self.wait(lambda: not (self.fresh("HEARTBEAT").base_mode & M.MAV_MODE_FLAG_SAFETY_ARMED), timeout)
        LOG.info("Landung beendet, Motoren disarmt")
