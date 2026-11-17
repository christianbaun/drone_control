# SPDX-License-Identifier: Apache-2.0
"""Test telemetry rendering, freshness rules, and dashboard data requests.

File: tests/test_telemetry.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pymavlink import mavutil
from drone_control.telemetry import render, watch, terminal_frame
from drone_control.vehicle import Vehicle


class TelemetryTests(unittest.TestCase):
    def test_units_and_unknown_battery(self):
        cache = {kind: (SimpleNamespace(**fields), 10) for kind, fields in {
            'GLOBAL_POSITION_INT': dict(relative_alt=500, vx=300, vy=400, vz=-25),
            'ATTITUDE': dict(roll=math.pi / 6, pitch=-math.pi / 4, yaw=0),
            'DISTANCE_SENSOR_DOWN': dict(min_distance=10, max_distance=800, current_distance=48),
            'SYS_STATUS': dict(voltage_battery=65535, current_battery=-1, battery_remaining=-1),
        }.items()}
        output = render(cache, now=11)
        for value in ['0.50 m', '0.48 m', '30.0 °', '-45.0 °', '5.00 m/s', '0.25 m/s', 'Batterie: — | — | —']:
            self.assertIn(value, output)

    def test_ekf_shows_readable_warnings_without_type_or_bitmask(self):
        for flags, expected in [(895, 'keine Warnflags gemeldet'),
                                (33663, 'GPS unplausibel (GPS_GLITCHING)'),
                                (1024, 'Filter nicht initialisiert'),
                                (128, 'Konstantpositionsmodus')]:
            with self.subTest(flags=flags):
                text = render({'EKF_STATUS_REPORT': (SimpleNamespace(flags=flags), 10)}, now=10)
                self.assertIn(expected, text)
                self.assertNotIn('EKF-Typ', text)
                self.assertNotIn('EKF-Statusbits', text)

    def test_source_set_message_and_age_without_pwm_row(self):
        cache = {'EKF_SOURCE_SET_TEXT': ('Using EKF Source Set 3', 5)}
        text = render(cache, now=11)
        self.assertIn('3 (Optical Flow / Entfernungssensor', text)
        self.assertIn('vor 6 s', text)
        self.assertNotIn('RC Kanal 8', text)

    def test_source_set_unknown_without_message(self):
        self.assertIn('Umschaltmeldung): unbekannt', render({}, now=10))

    def test_source_switch_message_is_retained(self):
        transport = Mock()
        with patch('drone_control.vehicle.mavutil.mavlink_connection', return_value=transport):
            vehicle = Vehicle('unused')
        for text in [b'Using EKF Source Set 2', b'Other message']:
            msg = mavutil.mavlink.MAVLink_statustext_message(6, text)
            msg._header.srcSystem, msg._header.srcComponent = 1, 1
            transport.recv_match.return_value = msg
            vehicle.pump()
        self.assertEqual(vehicle.cache['EKF_SOURCE_SET_TEXT'][0], 'Using EKF Source Set 2')

    def test_stale_data_is_hidden(self):
        cache = {'ATTITUDE': (SimpleNamespace(roll=1, pitch=1, yaw=1), 0)}
        self.assertIn('Roll: — | Pitch: — | Yaw: —', render(cache, now=4))
        self.assertIn('KEIN FRISCHER HEARTBEAT', render(cache, now=4))

    def test_invalid_range_is_hidden(self):
        for distance, quality in [(900, 100), (50, 1)]:
            msg = SimpleNamespace(min_distance=10, max_distance=800,
                                  current_distance=distance, signal_quality=quality)
            self.assertIn('Messachse): —', render({'DISTANCE_SENSOR_DOWN': (msg, 10)}, now=10))

    def test_unknown_signal_quality_keeps_valid_distance(self):
        msg = SimpleNamespace(min_distance=10, max_distance=800,
                              current_distance=48, signal_quality=0)
        self.assertIn('Messachse): 0.48 m', render({'DISTANCE_SENSOR_DOWN': (msg, 10)}, now=10))

    def test_terminal_clears_each_line(self):
        self.assertEqual(terminal_frame('Yaw: 1 °\nRoll: 0 °'),
                         '\033[H\033[2KYaw: 1 °\r\n\033[2KRoll: 0 °\033[J')

    def test_missing_distance_has_diagnostic(self):
        self.assertIn('keine frische DISTANCE_SENSOR-Nachricht', render({}, now=10))

    def test_only_downward_sensor_updates_ground_distance(self):
        transport = Mock()
        with patch('drone_control.vehicle.mavutil.mavlink_connection', return_value=transport):
            vehicle = Vehicle('unused')
        for orientation in [25, 0]:
            msg = mavutil.mavlink.MAVLink_distance_sensor_message(0, 10, 800, 50, 0, 1, orientation, 0)
            msg._header.srcSystem, msg._header.srcComponent = 1, 1
            transport.recv_match.return_value = msg
            vehicle.pump()
            self.assertEqual(vehicle.cache['DISTANCE_SENSOR_DOWN'][0].orientation, 25)

    def test_passive_watch_sends_nothing(self):
        vehicle = Mock()
        vehicle.pump.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            watch(vehicle, request_streams=False)
        vehicle.send_command.assert_not_called()

    def test_arming_messages_remain_visible_with_age(self):
        output = render({'ARMING_MESSAGES': [('PreArm: Battery 1 low voltage', 10)]}, now=20)
        self.assertIn('Arming-Hinweis (FC, vor 10 s): PreArm: Battery 1 low voltage', output)
