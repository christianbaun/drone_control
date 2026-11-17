# SPDX-License-Identifier: Apache-2.0
"""Load and validate local battery display profiles without changing FC settings.

File: drone_control/battery.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

from dataclasses import dataclass
import tomllib


@dataclass(frozen=True)
class BatteryProfile:
    chemistry: str
    cells: int
    capacity_mah: int

    def __post_init__(self):
        if self.chemistry not in ('Li-Ion', 'LiPo', 'LiFePO4'):
            raise ValueError('Unbekannter Akkutyp im Anzeigeprofil')
        if type(self.cells) is not int or not 1 <= self.cells <= 24:
            raise ValueError('Zellenzahl muss zwischen 1 und 24 liegen')
        if type(self.capacity_mah) is not int or not 1 <= self.capacity_mah <= 100000:
            raise ValueError('Ungültige Akkukapazität')

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as stream:
            return cls(**tomllib.load(stream))

    def describe(self, voltage):
        average = f'{voltage / self.cells:.2f} V/Zelle' if voltage is not None else '— V/Zelle'
        return f'Ø {average} | {self.chemistry} {self.cells}S · {self.capacity_mah} mAh'
