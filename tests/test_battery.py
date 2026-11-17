# SPDX-License-Identifier: Apache-2.0
"""Test battery profile parsing, validation, and display descriptions.

File: tests/test_battery.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import unittest
from types import SimpleNamespace as NS
from drone_control.battery import BatteryProfile
from drone_control.telemetry import render


class BatteryTests(unittest.TestCase):
    def test_four_cell_average_and_profile(self):
        profile = BatteryProfile('Li-Ion', 4, 2500)
        text = render({'SYS_STATUS': (NS(voltage_battery=15400, current_battery=33,
                                        battery_remaining=97), 10)}, 10, profile)
        self.assertIn('3.85 V/Zelle', text)
        self.assertIn('Li-Ion 4S · 2500 mAh', text)
        self.assertIn('97 %', text)

    def test_missing_voltage_does_not_become_zero(self):
        self.assertIn('— V/Zelle', BatteryProfile('Li-Ion', 4, 2500).describe(None))

    def test_invalid_profile(self):
        for cells in [0, 25, True, 4.5]:
            with self.subTest(cells=cells), self.assertRaises(ValueError):
                BatteryProfile('Li-Ion', cells, 2500)
