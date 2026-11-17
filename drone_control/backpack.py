# SPDX-License-Identifier: Apache-2.0
"""Discover TX Backpack HTTP diagnostics and MAVLink UDP endpoints.

File: drone_control/backpack.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import json
import socket
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler


def discover(address):
    url = urlsplit(address if '://' in address else 'http://' + address)
    if url.scheme != 'http' or not url.hostname or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment:
        raise ValueError('--backpack erwartet einen Hostnamen oder http://HOST/ ohne Zugangsdaten')
    try:
        ip = socket.gethostbyname(url.hostname)
        # Lokale Geräte nicht über einen konfigurierten HTTP-Proxy ansprechen.
        opener = build_opener(ProxyHandler({}))
        authority = ip + (f':{url.port}' if url.port else '')
        with opener.open(f'http://{authority}/mavlink', timeout=5) as response:
            data = json.loads(response.read(16384))
    except (OSError, ValueError) as error:
        raise RuntimeError(f'Backpack {url.hostname} nicht auslesbar: {error}. '
                           'Gleiches WLAN prüfen; bei fehlendem mDNS die IP aus dem Router verwenden.') from error
    if not isinstance(data, dict) or data.get('enabled') is not True:
        raise RuntimeError('Backpack erreichbar, aber MAVLink-Weiterleitung nicht aktiv. '
                           'ELRS-Menü: Backpack → Telemetry → WiFi wählen; '
                           'Falls WiFi bereits angezeigt wird: Telemetry einmal auf Off und zurück auf WiFi setzen. '
                           'Die Diagnose des Backpacks meldet enabled=false; der Menüwert allein bestätigt den Betriebsmodus nicht.')
    ports = data.get('ports', {})
    if not isinstance(ports, dict):
        raise ValueError('Backpack meldet ungültige UDP-Ports')
    for name in ('listen', 'send'):
        value = ports.get(name)
        if type(value) is not int or not 1 <= value <= 65535:
            raise ValueError(f'Backpack meldet ungültigen UDP-Port: {name}')
    return ip, ports['listen'], ports['send']
