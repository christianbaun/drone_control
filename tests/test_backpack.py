# SPDX-License-Identifier: Apache-2.0
"""Test Backpack discovery, diagnostic validation, and endpoint handling.

File: tests/test_backpack.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import json
import unittest
from unittest.mock import Mock, patch
from drone_control.backpack import discover
from drone_control.vehicle import Vehicle


class BackpackTests(unittest.TestCase):
    def discovery(self, data):
        response = Mock()
        response.read.return_value = json.dumps(data).encode()
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = context
        with patch('drone_control.backpack.socket.gethostbyname', return_value='10.0.0.42'), \
             patch('drone_control.backpack.build_opener', return_value=opener):
            result = discover('http://elrs_txbp.local/')
        opener.open.assert_called_once_with('http://10.0.0.42/mavlink', timeout=5)
        return result

    def test_ports_from_device(self):
        self.assertEqual(self.discovery({'enabled': True, 'ports': {'listen': 14555, 'send': 14550}}),
                         ('10.0.0.42', 14555, 14550))

    def test_disabled_forwarding_explains_radio_setting(self):
        with self.assertRaisesRegex(RuntimeError, 'Telemetry → WiFi'):
            self.discovery({'enabled': False})

    def test_invalid_ports(self):
        for port in [0, 65536, '14555', True]:
            with self.subTest(port=port), self.assertRaises(ValueError):
                self.discovery({'enabled': True, 'ports': {'listen': port, 'send': 14550}})

    def test_bad_addresses(self):
        for address in ['https://elrs_txbp.local', 'http://host/settings', 'http://user:pass@host/']:
            with self.subTest(address=address), self.assertRaises(ValueError):
                discover(address)

    def test_mdns_failure_suggests_ip(self):
        with patch('drone_control.backpack.socket.gethostbyname', side_effect=OSError('not found')):
            with self.assertRaisesRegex(RuntimeError, 'IP aus dem Router'):
                discover('elrs_txbp.local')

    def test_registration_uses_ping_without_heartbeat_or_commands(self):
        transport = Mock()
        transport.clients = set()
        with patch('drone_control.vehicle.mavutil.mavlink_connection', return_value=transport):
            vehicle = Vehicle('udpin:0.0.0.0:14550')
        vehicle.register_backpack(('10.0.0.42', 14555))
        self.assertIn(('10.0.0.42', 14555), transport.clients)
        transport.mav.ping_send.assert_called_once()
        transport.mav.heartbeat_send.assert_not_called()
        transport.mav.command_long_send.assert_not_called()
        self.assertFalse(vehicle.heartbeat_enabled)
