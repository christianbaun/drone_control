# SPDX-License-Identifier: Apache-2.0
"""Test GPS, heading, and magnetometer formatting and invalid-data handling.

File: tests/test_navigation.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import math
import unittest
from types import SimpleNamespace as NS
from drone_control.navigation import heading, navigation_lines


class NavigationTests(unittest.TestCase):
    def gps(self, **changes):
        values = dict(fix_type=3, satellites_visible=12, eph=125, epv=200,
                      lat=501234567, lon=86543210, alt=123450, cog=13800, h_acc=850)
        values.update(changes)
        return NS(**values)

    def text(self, **messages):
        return '\n'.join(navigation_lines(messages.get))

    def test_heading_wrap_and_directions(self):
        for value, direction in [(0, 'N'), (360, 'N'), (-90, 'W'), (138, 'SO'), (90, 'O')]:
            self.assertIn(f'({direction})', heading(value))
        self.assertEqual(heading(math.nan), '—')

    def test_gps_units(self):
        text = self.text(GPS_RAW_INT=self.gps())
        for expected in ['50.1234567, 8.6543210', '123.45 m MSL', '0.85 m',
                         'Satelliten=12', 'HDOP=1.25', '138.0 ° (SO)']:
            self.assertIn(expected, text)

    def test_no_fix_hides_old_coordinates(self):
        text = self.text(GPS_RAW_INT=self.gps(fix_type=1, satellites_visible=255, eph=65535, epv=65535))
        self.assertIn('GPS-Position: —', text)
        self.assertIn('GPS-Höhe: —', text)
        self.assertIn('HDOP=—', text)
        self.assertNotIn('50.1234567', text)

    def test_two_dimensional_fix_has_no_altitude(self):
        self.assertIn('GPS-Höhe: —', self.text(GPS_RAW_INT=self.gps(fix_type=2)))

    def test_unknown_course_and_accuracy(self):
        text = self.text(GPS_RAW_INT=self.gps(cog=65535, h_acc=0))
        self.assertIn('GPS-Bewegungskurs: —', text)
        self.assertIn('Genauigkeit (Empfänger): —', text)

    def test_heading_is_separate_from_course(self):
        text = self.text(GPS_RAW_INT=self.gps(cog=9000), ATTITUDE=NS(yaw=math.pi))
        self.assertIn('FC-Schätzung): 180.0 ° (S)', text)
        self.assertIn('GPS-Bewegungskurs: 90.0 ° (O)', text)

    def test_magnetometer_status_and_field(self):
        text = self.text(SYS_STATUS=NS(onboard_control_sensors_present=4,
            onboard_control_sensors_enabled=4, onboard_control_sensors_health=4),
            SCALED_IMU=NS(xmag=300, ymag=400, zmag=0))
        self.assertIn('gesund laut FC', text)
        self.assertIn('Betrag=500.0 mG', text)
        self.assertIn('Magnetometer: —', self.text())
