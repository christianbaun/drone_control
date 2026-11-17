# SPDX-License-Identifier: Apache-2.0
"""Test mission input validation and flight sequence orchestration.

File: tests/test_mission.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import math
import unittest
from drone_control.mission import Mission, fly


class FakeVehicle:
    def __init__(self, interrupt=False):
        self.calls = []
        self.interrupt = interrupt

    def preflight(self): self.calls.append("preflight")
    def arm(self): self.calls.append("arm")
    def takeoff(self, *args): self.calls.append("takeoff")
    def hold(self, *args):
        self.calls.append("hold")
        if self.interrupt:
            raise RuntimeError("RC takeover")
    def land(self, *args): self.calls.append("land")


class MissionTests(unittest.TestCase):
    def test_sequence(self):
        vehicle = FakeVehicle()
        fly(vehicle, Mission())
        self.assertEqual(vehicle.calls, ["preflight", "arm", "takeoff", "hold", "land"])

    def test_no_land_command_after_takeover(self):
        vehicle = FakeVehicle(interrupt=True)
        with self.assertRaises(RuntimeError):
            fly(vehicle, Mission())
        self.assertNotIn("land", vehicle.calls)

    def test_reject_invalid_mission(self):
        for value in [-1, 0, 5, math.nan, math.inf, True, "0.5"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Mission(height_m=value)


if __name__ == "__main__":
    unittest.main()
