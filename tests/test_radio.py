# SPDX-License-Identifier: Apache-2.0
"""Test RC signal diagnostics and interpretation of VTX settings.

File: tests/test_radio.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from pymavlink import mavutil
from drone_control.radio import radio_lines, vtx_lines, VTX_PARAMS
from drone_control.vehicle import Vehicle


class RadioTests(unittest.TestCase):
    def test_rc_rssi_scaling_and_unknown(self):
        for rssi, expected in [(254, '100 %'), (127, '50 %'), (0, '0 %'), (255, 'kein RC-RSSI')]:
            with self.subTest(rssi=rssi):
                text = '\n'.join(radio_lines({'RC_CHANNELS': NS(rssi=rssi)}.get))
                self.assertIn(expected, text)
                self.assertNotIn('LQ=', text)

    def test_radio_module_has_separate_source_and_cannot_override(self):
        transport = Mock()
        with patch('drone_control.vehicle.mavutil.mavlink_connection', return_value=transport):
            vehicle = Vehicle('unused')
        radio = mavutil.mavlink.MAVLink_radio_status_message(100, 90, 50, 20, 10, 3, 2)
        radio._header.srcSystem, radio._header.srcComponent = 51, 68
        transport.recv_match.return_value = radio
        vehicle.pump()
        self.assertIn('RADIO_STATUS', vehicle.cache)
        text = '\n'.join(radio_lines({'RADIO_STATUS': radio}.get))
        self.assertIn('[51/68]', text)
        self.assertNotIn('dBm', text)
        self.assertNotIn('HEARTBEAT', vehicle.cache)
        self.assertFalse(vehicle.overridden)

    def test_vtx_units_channel_index_and_pitmode(self):
        values = [1, 5800, 4, 3, 25, 1]
        cache = {name: (NS(param_value=value), 10) for name, value in zip(VTX_PARAMS, values)}
        text = '\n'.join(vtx_lines(cache, 11))
        for expected in ['5800 MHz', 'RaceBand', 'Kanal 4', '25 mW', 'Pit-Mode (FC): AN']:
            self.assertIn(expected, text)
        self.assertIn('VTX-Leistung (FC): PIT (mW unbekannt; normal: 25 mW)', text)
        self.assertNotIn('VTX-Leistung (FC): 25 mW', text)
        self.assertIn('keine frische', vtx_lines(cache, 46)[0])

    def test_vtx_power_with_pit_off_or_stale(self):
        cache = {name: (NS(param_value=value), 10)
                 for name, value in zip(VTX_PARAMS, [1, 5800, 4, 3, 25, 0])}
        self.assertIn('VTX-Leistung (FC): 25 mW | Pit-Mode (FC): AUS',
                      '\n'.join(vtx_lines(cache, 11)))
        cache['VTX_OPTIONS'] = (NS(param_value=1), -30)
        text = '\n'.join(vtx_lines(cache, 11))
        self.assertIn('VTX-Leistung (FC): — (Normalleistung: 25 mW)', text)
        self.assertIn('Pit-Mode (FC): —', text)

    def test_vtx_disabled_and_partial(self):
        self.assertIn('deaktiviert', vtx_lines({'VTX_ENABLE': (NS(param_value=0), 10)}, 10)[0])
        text = '\n'.join(vtx_lines({'VTX_ENABLE': (NS(param_value=1), 10)}, 10))
        self.assertIn('Band —', text)
        self.assertIn('Pit-Mode (FC): —', text)

    def test_only_target_fc_can_supply_vtx_parameters(self):
        transport = Mock()
        with patch('drone_control.vehicle.mavutil.mavlink_connection', return_value=transport):
            vehicle = Vehicle('unused')
        msg = mavutil.mavlink.MAVLink_param_value_message(b'VTX_FREQ', 5800, 9, 100, 0)
        msg._header.srcSystem, msg._header.srcComponent = 42, 1
        transport.recv_match.return_value = msg
        vehicle.pump()
        self.assertNotIn('VTX_FREQ', vehicle.cache)
        msg._header.srcSystem = 1
        vehicle.pump()
        self.assertEqual(vehicle.cache['VTX_FREQ'][0].param_value, 5800)
