# SPDX-License-Identifier: Apache-2.0
"""Validate TOML missions and execute the arm, takeoff, hold, and land sequence.

File: drone_control/mission.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

from dataclasses import dataclass
import math
import tomllib


@dataclass(frozen=True)
class Mission:
    height_m: float = 0.5
    hold_s: float = 5.0
    takeoff_timeout_s: float = 30.0
    landing_timeout_s: float = 60.0

    def __post_init__(self):
        limits = {"height_m": (0.3, 3), "hold_s": (0, 120),
                  "takeoff_timeout_s": (5, 120), "landing_timeout_s": (10, 180)}
        for key, (low, high) in limits.items():
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key}: Zahl erforderlich")
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{key}: erlaubt sind {low} bis {high}")

    @classmethod
    def load(cls, path):
        with open(path, "rb") as stream:
            return cls(**tomllib.load(stream))


def fly(vehicle, mission):
    """GUIDED wird vom Piloten gewählt; niemals automatisch zurückschalten."""
    vehicle.preflight()
    vehicle.arm()
    vehicle.takeoff(mission.height_m, mission.takeoff_timeout_s)
    vehicle.hold(mission.hold_s)
    vehicle.land(mission.landing_timeout_s)
