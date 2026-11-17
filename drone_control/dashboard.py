# SPDX-License-Identifier: Apache-2.0
"""Format telemetry as a responsive terminal dashboard with optional ANSI colors.

File: drone_control/dashboard.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import re
import textwrap

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def dashboard(text, width=100, height=30, color=True):
    width = max(12, width - 1)  # Letzte Spalte frei lassen: kein automatischer Umbruch.
    height = max(3, height - 1)

    def paint(value, code):
        return f'\033[{code}m{value}\033[0m' if color else value

    lines = text.splitlines()
    groups = {'FLUG & HÖHE': [], 'GPS & ORIENTIERUNG': [],
              'SENSOREN & BATTERIE': [], 'EKF & QUELLEN': []}
    status = next((line for line in lines if line.startswith('Verbindung:')), '')
    battery = next((line for line in lines if line.startswith('Batterie:')), 'Batterie: — | — | —')
    capacity = re.search(r'\|\s*(\d+(?:\.\d+)?)\s*%', battery)
    remaining = float(capacity.group(1)) if capacity else None
    battery_code = '1;33'
    battery_label = 'DATEN UNVOLLSTÄNDIG' if '—' in battery else 'RESTKAPAZITÄT UNBEKANNT'
    if remaining is not None and 0 <= remaining <= 100:
        if remaining <= 20:
            battery_code, battery_label = '1;37;41', 'AKKU NIEDRIG'
        elif remaining <= 30:
            battery_code, battery_label = '1;33', 'AKKU BEACHTEN'
        elif '—' not in battery:
            battery_code, battery_label = '1;32', 'FC-SCHÄTZUNG'
    battery_banner = battery.replace('Batterie:', 'AKKU', 1) + '  ·  ' + battery_label
    warning = []
    if 'KEIN FRISCHER HEARTBEAT' in status:
        warning.append('VERBINDUNG UNTERBROCHEN')
    for line in lines:
        if line.startswith('EKF-Status:'):
            for flag in ('GPS_GLITCHING', 'UNINITIALIZED', 'CONST_POS_MODE'):
                if flag in line:
                    warning.append(flag)
        if line.startswith(('Quadcopter-', 'Verbindung:', 'Batterie:', 'Arming-Hinweis', '— =')):
            continue
        if line.startswith(('GPS', 'Ausrichtung')):
            group = 'GPS & ORIENTIERUNG'
        elif line.startswith(('Magnet', 'Batterie', 'RC-Funk', 'Radio-', 'VTX')):
            group = 'SENSOREN & BATTERIE'
        elif line.startswith('EKF'):
            group = 'EKF & QUELLEN'
        else:
            group = 'FLUG & HÖHE'
        line = line.replace('EKF Source Set (letzte FC-Umschaltmeldung):', 'Source Set · letzte FC-Meldung:')
        line = line.replace('; Profil laut deiner Konfiguration', '; Profil laut Konfiguration')
        line = line.replace('Bodenabstand (Sensor, entlang Messachse):', 'Bodenabstand · Sensorachse:')
        groups[group].append(line)

    def styled(line):
        if any(word in line for word in ('FEHLER', 'GPS_GLITCHING', 'UNINITIALIZED', 'KEIN FRISCHER')):
            return paint(line, '1;31')
        if 'Pit-Mode (FC): AN' in line:
            # Cyan markiert einen aktiven Betriebsmodus, keine Warnung/Flugfreigabe.
            return line.replace('Pit-Mode (FC): AN', paint('Pit-Mode (FC): AN', '1;36'))
        fix = re.search(r'GPS: Fix=([^|]+)', line)
        if fix:
            value = fix.group(1).strip()
            if value in ('3D', 'DGPS', 'RTK Float', 'RTK Fixed', 'statisch', 'PPP'):
                code = '32'
            elif value in ('kein GPS', 'kein Fix'):
                code = '1;31'
            else:
                code = '33'
            token = 'Fix=' + value
            return line.replace(token, paint(token, code), 1)
        if '—' in line or 'unbekannt' in line or 'nicht ausgelesen' in line:
            return paint(line, '33')
        if 'ARMED' in line and 'DISARMED' not in line:
            return paint(line, '1;33')
        if 'Verbindung: OK' in line or 'gesund laut FC' in line:
            return paint(line, '32')
        return line

    def panel(title, content, size):
        result = [paint('┌─ ' + title + ' ' + '─' * max(0, size - len(title) - 5), '1;36')]
        for line in content:
            for part in textwrap.wrap(line, width=max(1, size - 2), replace_whitespace=True) or ['']:
                result.append(styled('│ ' + part))
        return result

    title = 'QUADCOPTER  /  LIVE-TELEMETRIE'
    output = [paint(title[:width], '1;36')]
    output.extend(paint(part, battery_code) for part in textwrap.wrap(battery_banner, width=width))
    output.extend(styled(part) for part in textwrap.wrap(status, width=width))
    for line in lines:
        if line.startswith('Arming-Hinweis'):
            output.extend(paint(part, '1;33') for part in textwrap.wrap(line, width=width))
    if warning:
        output.extend(paint(part, '1;31') for part in textwrap.wrap('! WARNUNG: ' + ' · '.join(warning), width=width))
    else:
        output.append(paint('● Live-Telemetrie · Anzeige ohne Flugsteuerung'[:width], '2'))
    if width >= 119:
        size = (width - 3) // 2
        names = list(groups)
        for left, right in [(names[0], names[1]), (names[2], names[3])]:
            a, b = panel(left, groups[left], size), panel(right, groups[right], size)
            for i in range(max(len(a), len(b))):
                first = a[i] if i < len(a) else ''
                second = b[i] if i < len(b) else ''
                padding = size - len(ANSI.sub('', first))
                output.append(first + ' ' * (padding + 3) + second)
    else:
        for name, content in groups.items():
            output.extend(panel(name, content, width))
    footer = 'Strg+C Beenden · — fehlt/veraltet · Farben: Rot Warnung, Gelb unbekannt'
    if len(output) + 1 > height:
        # Sicherheitsrelevante Warnungen stehen über den gekürzten Datenbereichen.
        output = output[:max(1, height - 2)]
        output.append(paint('Weitere Details: Terminal vergrößern oder Ausgabe in Datei umleiten.'[:width], '33'))
    output.append(paint(footer[:width], '2'))
    return '\n'.join(output)
