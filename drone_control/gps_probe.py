# SPDX-License-Identifier: Apache-2.0
"""Inspect UBX GPS messages through prepared USB passthrough using read-only queries.

File: drone_control/gps_probe.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import argparse
import time
import struct
from collections import Counter
import serial

POLL = bytes.fromhex('B5 62 0A 04 00 00 0E 34')


def checksum(data):
    a = b = 0
    for value in data:
        a = (a + value) & 255
        b = (b + a) & 255
    return bytes((a, b))


class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.valid = self.bad = 0

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while True:
            start = self.buffer.find(b'\xb5\x62')
            if start < 0:
                self.buffer[:] = self.buffer[-1:] if self.buffer.endswith(b'\xb5') else b''
                break
            del self.buffer[:start]
            if len(self.buffer) < 6:
                break
            size = int.from_bytes(self.buffer[4:6], 'little')
            if size > 4096:
                del self.buffer[0]
                continue
            if len(self.buffer) < size + 8:
                break
            packet = bytes(self.buffer[:size + 8])
            if checksum(packet[2:-2]) != packet[-2:]:
                self.bad += 1
                del self.buffer[0]
                continue
            self.valid += 1
            frames.append((packet[2], packet[3], packet[6:-2]))
            del self.buffer[:size + 8]
        return frames


def version(payload):
    if len(payload) < 40 or (len(payload) - 40) % 30:
        raise ValueError('MON-VER-Antwort hat keine erwartete Länge')
    def string(data):
        text = data.split(b'\0', 1)[0].decode('ascii', errors='replace')
        return ''.join(char if char.isprintable() else '?' for char in text)
    result = ['Software: ' + string(payload[:30]), 'Hardware: ' + string(payload[30:40])]
    result.extend('Zusatz: ' + string(payload[i:i+30]) for i in range(40, len(payload), 30))
    return '\n'.join(result)


def rate_settings(payload):
    if len(payload) != 6:
        raise ValueError('CFG-RATE-Antwort muss 6 Bytes enthalten')
    measure, navigation, reference = struct.unpack('<HHH', payload)
    hz = f'{1000 / measure:g} Hz' if measure else 'ungültig (0 ms)'
    match = (measure, navigation, reference) == (200, 1, 0)
    return (f'Messintervall: {measure} ms ({hz})\n'
            f'Navigationszyklen: {navigation}\nZeitreferenz: {reference} (0=UTC)\n'
            f'Entspricht ArduPilot-Ziel bei GPS1_RATE_MS=200: {"JA" if match else "NEIN"}')


def modern_rate(payload):
    # VALGET: Antwortversion 1, RAM-Layer 0, Position 0, ein U2-Schlüssel.
    if len(payload) != 10 or payload[:4] != bytes((1, 0, 0, 0)):
        raise ValueError('Unerwartete CFG-VALGET-Antwort')
    key, measure = struct.unpack('<IH', payload[4:])
    if key != 0x30210001 or measure == 0:
        raise ValueError('Falscher Schlüssel oder ungültiges Messintervall')
    return (f'CFG-RATE-MEAS aus aktivem GPS-RAM: {measure} ms ({1000 / measure:g} Hz)\n'
            'Die moderne Konfigurationsabfrage funktioniert; es wurden keine Werte geschrieben.')


def summarize(counts):
    names = {(10, 4): 'MON-VER', (6, 8): 'CFG-RATE', (6, 139): 'CFG-VALGET',
             (5, 0): 'ACK-NAK', (5, 1): 'ACK-ACK', (1, 7): 'NAV-PVT'}
    print('Empfangene UBX-Typen:')
    for (cls, ident), count in sorted(counts.items()):
        print(f'  {cls:02X}/{ident:02X} {names.get((cls, ident), "")}: {count}')


def listen(port, duration=6):
    print(f'Passiver Mitschnitt für {duration:g} Sekunden: keine Schreibzugriffe.', flush=True)
    decoder = Decoder()
    counts = Counter()
    port.reset_input_buffer()
    end = time.monotonic() + duration
    while time.monotonic() < end:
        for cls, ident, payload in decoder.feed(port.read(min(max(port.in_waiting, 1), 4096))):
            counts[(cls, ident)] += 1
            if (cls, ident) == (10, 4):
                print('MON-VER OHNE Anfrage empfangen.', flush=True)
    summarize(counts)
    if counts[(10, 4)]:
        print('Versionsmeldungen kommen ungefragt. Der frühere Versionstest allein beweist den Rückkanal nicht.')
    else:
        print('Keine ungefragte MON-VER im Beobachtungsfenster. Ein Rückkanalbeweis ist das allein noch nicht.')
    return bool(counts)


def probe(port, timeout=3, attempts=3, query='version'):
    queries = {'version': ('MON-VER', (10, 4), b'', version),
               'rate': ('CFG-RATE', (6, 8), b'', rate_settings),
               'rate-modern': ('CFG-VALGET', (6, 139),
                               bytes(4) + struct.pack('<I', 0x30210001), modern_rate)}
    name, target, request, describe = queries[query]
    body = bytes(target) + len(request).to_bytes(2, 'little') + request
    poll = b'\xb5\x62' + body + checksum(body)
    decoder = Decoder()
    received = 0
    counts = Counter()
    rejected = []
    for attempt in range(1, attempts + 1):
        # Bereits gepufferte Startmeldungen sind keine Antwort auf unsere Anfrage.
        port.reset_input_buffer()
        decoder.buffer.clear()
        print(f'{name}-Abfrage {attempt}/{attempts} senden …', flush=True)
        if port.write(poll) != len(poll):
            raise OSError(f'{name}-Anfrage nicht vollständig geschrieben')
        port.flush()
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            data = port.read(min(max(port.in_waiting, 1), 4096))
            received += len(data)
            for cls, message_id, payload in decoder.feed(data):
                counts[(cls, message_id)] += 1
                if cls == 5 and message_id in (0, 1):
                    label = 'ACK-ACK' if message_id == 1 else 'ACK-NAK'
                    command = f'{payload[0]:02X}/{payload[1]:02X}' if len(payload) == 2 else 'unerwartete Nutzdaten'
                    match = ' (passt zu unserer Anfrage)' if payload == bytes(target) else ' (andere Befehlskennung)'
                    print(f'UBX-{label} für {command}{match}; Nutzdaten: {payload.hex()}', flush=True)
                    if message_id == 1 and payload == bytes(target):
                        print('GPS bestätigt die Befehlskennung. Das ist noch keine Antwort mit Konfigurationswerten.', flush=True)
                if (cls, message_id) == (5, 0) and payload == bytes(target):
                    print(f'GPS hat {name} mit UBX-ACK-NAK abgelehnt. Rückkanal funktioniert; '
                          'diese Anfrage wird in diesem Zustand nicht akzeptiert.')
                    return False
                if (cls, message_id) == target:
                    try:
                        description = describe(payload)
                    except ValueError as error:
                        rejected.append(f"{error}: {payload[:80].hex()}")
                        continue
                    print(f'Gültige UBX-{name}-Antwort nach Anfrage empfangen.\n' + description)
                    print('Starker Hinweis auf funktionierenden Hin-/Rückweg über diesen Passthrough.\n'
                          'Dies bestätigt noch nicht die Unterstützung aller ArduPilot-Konfigurationsbefehle.')
                    return True
    summarize(counts)
    for detail in rejected[-3:]:
        print("Empfangene, aber nicht passende Antwort: " + detail)
    print(f'Keine gültige {name}-Antwort. Empfang: {received} Bytes, '
          f'{decoder.valid} gültige UBX-Pakete, {decoder.bad} Prüfsummenfehler.\n'
          'Kein Beweis für Kabeldefekt: Passthrough, tatsächliche GPS-Baudrate und Unterstützung der angefragten UBX-Nachricht prüfen.')
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog='Vorbereitung: docs/gps-test.md. '
                                     'Nur disarmt und ohne Propeller; MicoConfigurator vorher trennen.')
    parser.add_argument('--port', required=True, help='USB-Datenport des FC, z. B. /dev/ttyACM0')
    parser.add_argument('--baud', type=int, default=230400, choices=[115200, 230400],
                        help='Muss zur GPS-/Passthrough-Baudrate passen (Standard: 230400)')
    parser.add_argument('--query', choices=['version', 'rate', 'rate-modern', 'listen'], default='version',
                        help='Version, CFG-RATE, CFG-VALGET oder passiver Mitschnitt ohne Anfragen')
    args = parser.parse_args()
    try:
        with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=2, exclusive=True) as port:
            print(f'USB-Passthrough: {args.port}, {args.baud} Baud; nur lesende GPS-Abfrage.', flush=True)
            if args.query == 'listen':
                return 0 if listen(port) else 1
            return 0 if probe(port, query=args.query) else 1
    except (OSError, serial.SerialException) as error:
        print(f'Fehler: {error}. USB-Port, Zugriffsrechte und andere Programme prüfen.')
        return 1
    except KeyboardInterrupt:
        print('\nAbfrage beendet.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
