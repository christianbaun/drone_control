# SPDX-License-Identifier: Apache-2.0
"""Interpret RC radio diagnostics and VTX settings without modifying them.

File: drone_control/radio.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import math

VTX_PARAMS = ('VTX_ENABLE', 'VTX_FREQ', 'VTX_BAND', 'VTX_CHANNEL', 'VTX_POWER', 'VTX_OPTIONS')


def radio_lines(message):
    rc = message('RC_CHANNELS')
    if rc is None:
        rc = message('RC_CHANNELS_RAW')
    rssi = getattr(rc, 'rssi', 255)
    signal = f'{rssi / 254 * 100:.0f} % (FC-RSSI, normiert)' if 0 <= rssi <= 254 else '— (kein RC-RSSI empfangen)'
    lines = [f'RC-Funksignal: {signal}']
    radio = message('RADIO_STATUS')
    if radio is not None:
        def raw(value):
            return str(value) if 0 <= value <= 254 else '—'
        lines.append(f'Radio-Status [{radio.get_srcSystem()}/{radio.get_srcComponent()}]: '
                     f'RSSI lokal={raw(radio.rssi)}, fern={raw(radio.remrssi)} (gerätespezifische Skala)')
        lines.append(f'Radio-Puffer frei: {radio.txbuf} % | Empfangsfehler: {radio.rxerrors} | '
                     f'korrigiert: {radio.fixed}')
    return lines


def vtx_lines(cache, now):
    def param(name):
        pair = cache.get(name)
        if pair is None or now - pair[1] > 35:
            return None
        value = pair[0].param_value
        return int(value) if math.isfinite(value) else None

    enabled = param('VTX_ENABLE')
    if enabled is None:
        return ['VTX: — (keine frische VTX-Konfiguration vom FC)']
    if enabled == 0:
        return ['VTX: Unterstützung am FC deaktiviert (VTX_ENABLE=0)']
    freq, band, channel, power, options = [param(name) for name in VTX_PARAMS[1:]]
    bands = {0: 'A', 1: 'B', 2: 'E', 3: 'F/Airwave', 4: 'RaceBand', 5: 'LowRace'}
    band_text = bands.get(band, f'Index {band}') if band is not None else '—'
    channel_text = str(channel + 1) if channel is not None else '—'  # FC speichert 0-basiert.
    frequency = f'{freq} MHz' if freq is not None and freq > 0 else '—'
    watts = f'{power} mW' if power is not None and power >= 0 else '—'
    pit = ('AN' if options & 1 else 'AUS') if options is not None else '—'
    if pit == 'AN':
        watts = f'PIT (mW unbekannt; normal: {watts})'
    elif pit == '—':
        watts = f'— (Normalleistung: {watts})'
    return [f'VTX (FC-Einstellungen): {frequency} | Band {band_text} | Kanal {channel_text}',
            f'VTX-Leistung (FC): {watts} | Pit-Mode (FC): {pit}']
