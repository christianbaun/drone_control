# SPDX-License-Identifier: Apache-2.0
"""Test UBX framing, checksums, read-only queries, and response decoding.

File: tests/test_gps_probe.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import contextlib
import io
import unittest
from unittest.mock import Mock
from drone_control.gps_probe import POLL, Decoder, checksum, version, probe, rate_settings, modern_rate, listen


def packet(payload, cls=10, ident=4):
    data = bytes((cls, ident)) + len(payload).to_bytes(2, 'little') + payload
    return b'\xb5\x62' + data + checksum(data)


class GpsProbeTests(unittest.TestCase):
    def setUp(self):
        self.payload = b'B101 test'.ljust(30, b'\0') + b'0001'.ljust(10, b'\0')

    def test_poll_is_exact_read_only_mon_ver(self):
        self.assertEqual(POLL, packet(b''))
        self.assertEqual(POLL.hex(), 'b5620a0400000e34')

    def test_split_frame_and_noise(self):
        decoder = Decoder()
        reply = packet(self.payload)
        self.assertEqual(decoder.feed(b'noise' + reply[:1]), [])
        self.assertEqual(decoder.feed(reply[1:15]), [])
        self.assertEqual(decoder.feed(reply[15:]), [(10, 4, self.payload)])
        self.assertEqual(decoder.valid, 1)

    def test_bad_checksum_is_rejected_and_parser_recovers(self):
        decoder = Decoder()
        reply = packet(self.payload)
        self.assertEqual(decoder.feed(reply[:-1] + bytes((reply[-1] ^ 1,))), [])
        self.assertEqual(decoder.feed(reply), [(10, 4, self.payload)])
        self.assertEqual(decoder.bad, 1)

    def test_version_and_extensions(self):
        result = version(self.payload + b'PROTVER=27.00'.ljust(30, b'\0'))
        self.assertIn('Software: B101 test', result)
        self.assertIn('Hardware: 0001', result)
        self.assertIn('PROTVER=27.00', result)
        with self.assertRaises(ValueError):
            version(b'short')

    def test_probe_accepts_only_version_response_and_writes_only_poll(self):
        port = Mock(in_waiting=48)
        port.write.return_value = len(POLL)
        port.read.side_effect = [packet(b'other', 1, 7), packet(self.payload)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(probe(port))
        port.write.assert_called_once_with(POLL)
        self.assertIn('Gültige UBX-MON-VER-Antwort', output.getvalue())

    def test_no_data_does_not_prove_cable_failure(self):
        port = Mock()
        port.write.return_value = len(POLL)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(probe(port, timeout=0, attempts=1))
        self.assertIn('Kein Beweis für Kabeldefekt', output.getvalue())

    def test_read_rate_and_compare_target(self):
        import struct
        for values, expected in [((200, 1, 0), 'JA'), ((100, 1, 0), 'NEIN')]:
            self.assertIn('GPS1_RATE_MS=200: ' + expected, rate_settings(struct.pack('<HHH', *values)))
        port = Mock(in_waiting=14)
        port.write.return_value = 8
        port.read.return_value = packet(struct.pack('<HHH', 200, 1, 0), 6, 8)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(probe(port, query='rate'))
        port.write.assert_called_once_with(packet(b'', 6, 8))

    def test_nak_identifies_rejected_query(self):
        port = Mock(in_waiting=10)
        port.write.return_value = 8
        port.read.return_value = packet(bytes((6, 8)), 5, 0)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(probe(port, query='rate'))
        self.assertIn('UBX-ACK-NAK', output.getvalue())
        self.assertIn('Rückkanal funktioniert', output.getvalue())

    def test_modern_rate_uses_read_only_valget_and_checks_key(self):
        import struct
        payload = bytes((1, 0, 0, 0)) + struct.pack('<IH', 0x30210001, 200)
        self.assertIn('200 ms (5 Hz)', modern_rate(payload))
        port = Mock(in_waiting=18)
        port.write.return_value = 16
        port.read.return_value = packet(payload, 6, 139)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(probe(port, query='rate-modern'))
        port.write.assert_called_once_with(packet(bytes(4) + struct.pack('<I', 0x30210001), 6, 139))
        with self.assertRaises(ValueError):
            modern_rate(bytes((1, 0, 0, 0)) + struct.pack('<IH', 0x30210002, 200))

    def test_passive_capture_sends_nothing_and_detects_unsolicited_version(self):
        import itertools
        from unittest.mock import patch
        port = Mock(in_waiting=48)
        port.read.return_value = packet(self.payload)
        with patch('drone_control.gps_probe.time.monotonic', side_effect=itertools.count(0, 1)), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(listen(port, duration=3))
        port.write.assert_not_called()
        self.assertIn('MON-VER OHNE Anfrage', output.getvalue())
        self.assertIn('beweist den Rückkanal nicht', output.getvalue())

    def test_ack_identifies_target_without_counting_as_config_response(self):
        import itertools
        from unittest.mock import patch
        port = Mock(in_waiting=10)
        port.write.return_value = 16
        port.read.return_value = packet(bytes((6, 139)), 5, 1)
        with patch('drone_control.gps_probe.time.monotonic', side_effect=itertools.count(0, 0.25)), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(probe(port, timeout=1, attempts=1, query='rate-modern'))
        self.assertIn('ACK-ACK für 06/8B (passt zu unserer Anfrage)', output.getvalue())
        self.assertIn('noch keine Antwort mit Konfigurationswerten', output.getvalue())
