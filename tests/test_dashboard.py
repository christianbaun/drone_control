# SPDX-License-Identifier: Apache-2.0
"""Test dashboard layout, terminal formatting, and telemetry warning colors.

File: tests/test_dashboard.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import unittest
from drone_control.dashboard import dashboard, ANSI
from drone_control.telemetry import render


class DashboardTests(unittest.TestCase):
    def test_pit_active_color_and_plain_output(self):
        text = 'VTX-Leistung (FC): PIT (mW unbekannt; normal: 25 mW) | Pit-Mode (FC): AN'
        output = dashboard(text, 110, 40)
        self.assertIn('\033[1;36mPit-Mode (FC): AN\033[0m', output)
        self.assertNotIn('\033[33m', output)
        plain = dashboard(text, 110, 40, color=False)
        self.assertEqual(ANSI.sub('', output), plain)

    def test_small_terminal_stays_within_bounds(self):
        for width, height in [(40, 12), (80, 24), (120, 30), (160, 40)]:
            with self.subTest(width=width, height=height):
                output = ANSI.sub('', dashboard(render({}), width, height))
                self.assertLessEqual(len(output.splitlines()), height - 1)
                self.assertTrue(all(len(line) < width for line in output.splitlines()))

    def test_warning_visible_even_in_short_terminal(self):
        output = dashboard('Verbindung: OK\nEKF-Status: ATTITUDE, GPS_GLITCHING', 80, 10)
        self.assertIn('! WARNUNG: GPS_GLITCHING', output)
        self.assertIn('\033[1;31m', output)

    def test_no_color_and_full_details(self):
        output = dashboard(render({}), 160, 60, color=False)
        self.assertNotIn('\033[', output)
        for section in ['FLUG & HÖHE', 'GPS & ORIENTIERUNG', 'SENSOREN & BATTERIE', 'EKF & QUELLEN']:
            self.assertIn(section, output)
        self.assertIn('Source Set', output)

    def test_gps_fix_colors(self):
        for fix, code in [('3D', '32'), ('DGPS', '32'), ('RTK Fixed', '32'),
                          ('2D', '33'), ('—', '33'), ('kein Fix', '1;31'), ('kein GPS', '1;31')]:
            with self.subTest(fix=fix):
                output = dashboard(f'GPS: Fix={fix} | Satelliten=—', 100, 40)
                self.assertIn(f'\033[{code}mFix={fix}\033[0m', output)
                plain = dashboard(f'GPS: Fix={fix}', 100, 40, color=False)
                self.assertNotIn('\033[', plain)

    def test_battery_is_prominent_and_not_duplicated(self):
        output = dashboard('Batterie: 16.02 V | 0.33 A | 96 %', 100, 30)
        self.assertIn('AKKU 16.02 V', ANSI.sub('', output).splitlines()[1])
        self.assertEqual(output.count('16.02 V'), 1)
        self.assertIn('\033[1;32m', output)

    def test_battery_thresholds_and_missing_values(self):
        for percent, expected in [('20', 'AKKU NIEDRIG'), ('30', 'AKKU BEACHTEN'),
                                  ('31', 'FC-SCHÄTZUNG'), ('—', 'DATEN UNVOLLSTÄNDIG')]:
            with self.subTest(percent=percent):
                text = dashboard(f'Batterie: 16.00 V | 0.30 A | {percent} %', 100, 30)
                self.assertIn(expected, text)
                if percent == '20':
                    self.assertIn('\033[1;37;41m', text)
        partial = dashboard('Batterie: — | — | 96 %', 100, 30)
        self.assertNotIn('\033[1;32m', partial)

    def test_battery_remains_visible_in_small_terminal(self):
        output = dashboard('Batterie: 14.00 V | 5.00 A | 10 %\nEKF-Status: GPS_GLITCHING', 80, 10, False)
        self.assertIn('AKKU NIEDRIG', output)
        self.assertIn('GPS_GLITCHING', output)
