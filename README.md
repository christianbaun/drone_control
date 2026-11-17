# drone_control

[![Python ≥ 3.11](https://img.shields.io/badge/Python-%E2%89%A5%203.11-blue)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

[English](#english) · [Deutsch](#deutsch)

## English

A Python command-line tool for ArduCopter: display live telemetry, investigate arming failures, and execute a simple **arm → take off → hold → land** sequence. It connects through MAVLink, for example using ExpressLRS with a TX WiFi Backpack or a direct USB connection to the flight controller (FC).

**This software was developed with assistance from OpenAI Codex CLI.**

ArduPilot handles stabilization, state estimation, and motor control. The program runs locally on Debian Linux and requires no cloud service at runtime. The CLI help, logs, and dashboard currently use German; this README provides English instructions. The detailed guides linked below are currently in German.

> **Before flying:** Check connections and arming with propellers removed, test flight sequences in SITL first, and configure the FC failsafes. `run --execute` starts immediately after its checks pass. For RC takeover, switch to a different flight mode; moving the sticks alone does not reliably stop the sequence.

### Contents

- [Features and limitations](#features-and-limitations)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands and options](#commands-and-options)
- [Define a mission](#define-a-mission)
- [Prepare the flight controller](#prepare-the-flight-controller)
- [Telemetry and battery profile](#telemetry-and-battery-profile)
- [Troubleshooting](#troubleshooting)
- [Development and documentation](#development-and-documentation)
- [License](#license)

### Features and limitations

- Color terminal dashboard: battery, flight mode, altitude, ground distance, attitude, speed, GPS, magnetometer, RC RSSI, VTX settings, and EKF notices.
- Backpack discovery by hostname or IP, with UDP registration.
- Arming-only ground test with rejection messages from the FC.
- A vertical flight sequence configured in TOML.
- Stops sending commands after a detected RC/FC mode change; no automatic return to GUIDED or force-arming.

There is currently no waypoint navigation, obstacle avoidance, or graphical interface. Mission altitude is relative to **Home**, not a direct LiDAR ground-distance target. An exact 50 cm altitude is not guaranteed.

Connection, telemetry, and arming have been tried with a MicoAir743 V2, ArduCopter 4.6.2, ExpressLRS, and RadioMaster transmitters. Example hardware includes an MTF-01P optical-flow/range sensor and a GEPRC GEP-M10-DI GPS/compass. Other ArduPilot quadcopters may use the same interfaces, but compatibility must be verified. Successful arming does not establish reliable position holding or safe autonomous flight.

### Install

Requirements: **Python 3.11 or newer**, for example on Debian 12, and a working ArduCopter/MAVLink setup.

Clone or download this repository and open its directory, then run:

```bash
sudo apt install python3 python3-venv
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m drone_control --help
```

Installation includes `pymavlink` and `pyserial`. Run the examples from the repository directory. After installation, `.venv/bin/drone-control` is an alternative to `.venv/bin/python -m drone_control`.

### Quick start

#### 1. Preview without hardware

```bash
.venv/bin/python -m drone_control run --mission examples/hover.toml
```

Without `--execute`, `run` and `arm` do not open a connection. A preview is not a simulation.

#### 2. Connect the Backpack and display telemetry

Configure the transmitter and receiver for ExpressLRS MAVLink mode. On the transmitter, enable **Backpack → Telemetry → WiFi** and connect the laptop and Backpack to the same WiFi network.

```bash
.venv/bin/python -m drone_control status --backpack
.venv/bin/python -m drone_control telemetry --backpack
```

`--backpack` uses `elrs_txbp.local`. If mDNS resolution fails, use the current IP from your router:

```bash
.venv/bin/python -m drone_control telemetry --backpack 10.0.0.42
```

Replace this example IP. HTTP is used for discovery; MAVLink then uses UDP. Press `Ctrl+C` to stop the dashboard.

Other connection methods:

```bash
# Listen for incoming UDP telemetry on the laptop
.venv/bin/python -m drone_control telemetry --connect udpin:0.0.0.0:14550

# Direct USB connection to the FC; adjust device and baud rate
.venv/bin/python -m drone_control telemetry --connect /dev/ttyACM0 --baud 115200
```

For internal ELRS modules, choosing HID/SD/VCP on the radio's USB menu alone does not provide a bidirectional MAVLink bridge. Use Backpack WiFi for this setup; see the [connection guide (German)](docs/usage.md#usb-menü-der-fernsteuerung-hid-sd-oder-vcp).

#### 3. Test arming only

Ground test **with propellers removed**; disarm using the radio afterward:

```bash
.venv/bin/python -m drone_control arm --backpack --execute
```

The program keeps the current flight mode, sends no takeoff command, and exits after arming is confirmed. Motors may spin when armed. Automatic disarming and failsafes remain the FC's responsibility.

#### 4. Execute a flight sequence

First follow the [FC requirements](#prepare-the-flight-controller) and [testing guide (German)](docs/testing.md). Close the dashboard, **select GUIDED using the radio**, then run:

```bash
# Actual flight: starts immediately after the checks pass
.venv/bin/python -m drone_control run --backpack --mission examples/hover.toml --execute
```

On errors, link loss, or `Ctrl+C`, the program stops commands and mission heartbeats. It does not send a late LAND command after a possible RC takeover. The configured FC failsafe must handle the situation, subject to its timeout. A normal completed sequence requests LAND and waits for the FC to report disarmed motors.

### Commands and options

| Command | Behavior |
| --- | --- |
| `telemetry` | Live dashboard; automatically requests telemetry |
| `status` | Print the FC status once |
| `arm` | Preview arming; actually arm with `--execute` |
| `run` | Preview the mission; execute with `--execute` |

| Option | Purpose / default |
| --- | --- |
| `--backpack [HOST]` | Discover the Backpack; default host: `elrs_txbp.local` |
| `--connect ENDPOINT` | Alternative to `--backpack`; default: `udpin:0.0.0.0:14550` |
| `--baud BAUD` | Serial baud rate; `115200` |
| `--target-system ID` | FC MAVLink system ID; `1` |
| `--source-system ID` | Local MAVLink system ID; `255` |
| `--mission PATH` | TOML file for `run`; `examples/hover.toml` |
| `--execute` | Actually execute `arm` or `run` |
| `--battery-profile PATH` | Display profile for `telemetry`; `battery.toml` |
| `--passive` | For `telemetry`, skip UDP registration and MAVLink requests |
| `--help` | Help with further examples |

`--backpack --passive` still reads the HTTP diagnostics. Telemetry sends no GCS heartbeats or flight commands. The legacy `--request-streams` option remains accepted but is unnecessary.

### Define a mission

[examples/hover.toml](examples/hover.toml) configures the supported sequence. A custom file can specify:

```toml
height_m = 0.5
hold_s = 5.0
takeoff_timeout_s = 30.0
landing_timeout_s = 60.0
```

| Field | Meaning | Allowed range |
| --- | --- | --- |
| `height_m` | Target altitude in meters relative to Home | 0.3–3 |
| `hold_s` | Hold duration in seconds | 0–120 |
| `takeoff_timeout_s` | Takeoff timeout in seconds | 5–120 |
| `landing_timeout_s` | Landing/disarming timeout in seconds | 10–180 |

TOML configures a fixed sequence, not an arbitrary command list. Unknown fields and invalid values are rejected. Custom Python sequences can build on [mission.py](drone_control/mission.py).

### Prepare the flight controller

The program does not write persistent FC parameters. For `run --execute`, it checks, among other things:

- a disarmed quadcopter on the ground, with GUIDED already selected;
- fresh position, EKF, and ground-contact messages;
- enabled arming checks (`ARMING_CHECK != 0`) and RC failsafe (`FS_THR_ENABLE != 0`);
- GCS failsafe `FS_GCS_ENABLE = 5` (LAND), a timeout between 2 and 10 seconds, and a matching GCS system ID;
- `LAND_SPEED` between 10 and 30 cm/s.

Custom arming-check bitmasks are accepted and logged; the program does not assess whether the chosen checks suit the intended use. The `arm` command has fewer prerequisites than a flight sequence. See the [operating guide (German)](docs/usage.md#voraussetzungen-am-flugcontroller) for sensor fusion, takeover, and failsafe details.

### Telemetry and battery profile

The dashboard uses colors and adapts to terminal width. Missing, invalid, or more than three seconds old sensor data appears as `—`. Historical arming notices and EKF source-switch messages retain their reported age; they are not confirmation of the current state.

[battery.toml](battery.toml) is an **example profile for a 4S, 2500 mAh Li-Ion battery**. Adjust it for your battery:

```toml
chemistry = "Li-Ion"
cells = 4
capacity_mah = 2500
```

The profile adds average cell voltage (pack voltage / cell count). It changes neither FC percentages nor warning thresholds or failsafes. Battery highlighting currently depends only on the FC's remaining-capacity estimate: above 30% green, 21–30% yellow, up to 20% red; incomplete data yellow. This does not evaluate voltage or the weakest cell.

```bash
NO_COLOR=1 .venv/bin/python -m drone_control telemetry --backpack
```

Redirected output automatically omits colors and terminal control sequences. GPS, compass, RC RSSI, VTX, and EKF source details are explained in the [operating guide (German)](docs/usage.md#laufende-telemetrieanzeige).

#### Battery telemetry on the radio without this program

ExpressLRS uses `BATTERY_STATUS` for the EdgeTX sensors RxBt, Curr, Capa, and Bat%. The dashboard requests this message at 1 Hz. For persistent transmission on ArduCopter 4.6.2, save **`SRx_EXTRA3 = 1`** for the appropriate MAVLink connection and restart the FC.

The SR index does not necessarily match the UART number. In the tested configuration with USB, SERIAL4/MAVLink, SERIAL6/ELRS, and SERIAL8/MAVLink, use **`SR2_EXTRA3 = 1`**. Recheck the mapping for other port configurations. See the [persistent battery telemetry guide (German)](docs/usage.md#akkudaten-dauerhaft-an-edgetx-senden).

### Troubleshooting

| Problem | Next step |
| --- | --- |
| Cannot resolve `elrs_txbp.local` | Use the current router IP after `--backpack`; check mDNS |
| Backpack website works but forwarding is disabled | Toggle Telemetry Off, then WiFi on the radio; update WiFi is a different mode |
| No FC heartbeat | Check aircraft power, ELRS link, Telemetry/WiFi, UDP firewall, and WiFi client isolation; close other ground stations |
| UDP port already in use | Close another dashboard or ground station |
| Arming rejected | Resolve the specific FC message rather than disabling all checks |
| GPS fix but no position readiness | Check EKF source set, origin/Home, and sensor fusion; a 3D fix alone does not establish position holding |
| Battery only visible on the laptop | Check `BATTERY_STATUS` on the ELRS link or its saved EXTRA3 rate |
| Serial port inaccessible | Check device name and `dialout` membership; log in again after changing groups |

### Development and documentation

Run tests without connecting an aircraft:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover mission validation, MAVLink handling, RC takeover, telemetry, and Backpack discovery. They do not replace SITL and hardware testing.

| File / directory | Contents |
| --- | --- |
| [drone_control/](drone_control/) | CLI, connection, mission logic, and telemetry |
| [examples/](examples/) | Example missions |
| [tests/](tests/) | Unit tests |
| [docs/usage.md](docs/usage.md) | Detailed operating guide (German) |
| [docs/testing.md](docs/testing.md) | Testing procedure and SITL notes (German) |
| [docs/gps-test.md](docs/gps-test.md) | Read-only UBX diagnostics via USB passthrough (German) |

This project was developed with assistance from **OpenAI Codex CLI**, including code and documentation.

Source files, tests, and TOML configuration files carry headers describing their purpose, project version, header date, contributors, Codex CLI assistance, and Apache-2.0 license. The version refers to the package version in `pyproject.toml`; update it consistently when releasing a new project version. The header date records when the header was added, not the file creation date.

Bug reports should include the command, error message, Python/ArduCopter/ELRS/Backpack versions, and connection method. Remove location coordinates and WiFi credentials before publishing. Contributions should include a clear description and appropriate tests.

References: [ArduPilot GUIDED](https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html), [GCS failsafe](https://ardupilot.org/copter/docs/gcs-failsafe.html), [ExpressLRS MAVLink](https://www.expresslrs.org/software/mavlink/).

### License

This project is licensed under the **Apache License, Version 2.0**. See [LICENSE](LICENSE) for the full text. Dependencies retain their respective licenses.

---

## Deutsch

Ein Python-Kommandozeilenprogramm für ArduCopter: Live-Telemetrie anzeigen, Arming-Probleme untersuchen und einen einfachen Ablauf **Armen → Starten → Halten → Landen** ausführen. Die Verbindung erfolgt über MAVLink, beispielsweise mit ExpressLRS und einem TX-WiFi-Backpack oder direkt per USB am Flugcontroller.

**Diese Software wurde unter Mithilfe von OpenAI Codex CLI erstellt.**

ArduPilot übernimmt Stabilisierung, Positionsschätzung und Motorregelung. Das Programm läuft lokal unter Debian Linux und benötigt keinen Cloud-Dienst.

> **Vor dem Flugbetrieb:** Verbindungen und Arming ohne Propeller prüfen, Flugabläufe zunächst in SITL testen und die FC-Failsafes konfigurieren. `run --execute` startet nach erfolgreichen Vorprüfungen unmittelbar. Zur RC-Übernahme in einen anderen Flugmodus schalten; Stickbewegungen allein beenden den Ablauf nicht zuverlässig.

### Inhalt

- [Funktionen und Grenzen](#funktionen-und-grenzen)
- [Installation](#installation)
- [Schnellstart](#schnellstart)
- [Befehle und Optionen](#befehle-und-optionen)
- [Missionen definieren](#missionen-definieren)
- [Flugcontroller vorbereiten](#flugcontroller-vorbereiten)
- [Telemetrie und Akkuprofil](#telemetrie-und-akkuprofil)
- [Fehlersuche](#fehlersuche)
- [Entwicklung und Dokumentation](#entwicklung-und-dokumentation)
- [Lizenz](#lizenz)

### Funktionen und Grenzen

- Farbiges Terminal-Dashboard mit Akku, Flugmodus, Höhe, Bodenabstand, Lage, Geschwindigkeit, GPS, Magnetometer, RC-RSSI, VTX-Einstellungen und EKF-Hinweisen.
- Backpack-Erkennung über Hostname oder IP mit UDP-Anmeldung.
- Arming-Bodentest mit konkreten Ablehnungsgründen des Flugcontrollers.
- Konfigurierbarer vertikaler Flugablauf aus einer TOML-Datei.
- Abbruch bei erkanntem RC-/FC-Moduswechsel; kein automatisches Zurückschalten auf GUIDED und kein Force-Arming.

Die Software bietet derzeit keine Wegpunktnavigation, Hindernisvermeidung oder grafische Oberfläche. Die Zielhöhe einer Mission bezieht sich auf **Home**, nicht direkt auf den LiDAR-Bodenabstand. Eine exakt eingehaltene Höhe von 50 cm wird nicht garantiert.

Verbindung, Telemetrie und Armen wurden mit einem MicoAir743 V2, ArduCopter 4.6.2, ExpressLRS und RadioMaster-Sendern erprobt. Zur Beispielausstattung gehören ein MTF-01P für Optical Flow/Entfernung und ein GEPRC GEP-M10-DI für GPS/Kompass. Andere ArduPilot-Quadcopter können dieselben Schnittstellen verwenden; ihre Kompatibilität muss geprüft werden. Erfolgreiches Armen ist kein Nachweis für sichere Positionshaltung oder einen sicheren Missionsflug.

### Installation

Voraussetzungen: Python **3.11 oder neuer**, beispielsweise unter Debian 12, sowie eine funktionierende ArduCopter-/MAVLink-Konfiguration.

Repository klonen oder herunterladen und in das Projektverzeichnis wechseln. Danach:

```bash
sudo apt install python3 python3-venv
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m drone_control --help
```

Die Installation richtet `pymavlink` und `pyserial` ein. Alle Beispiele werden im Projektverzeichnis ausgeführt. Alternativ zu `.venv/bin/python -m drone_control` ist nach der Installation `.venv/bin/drone-control` verfügbar.

### Schnellstart

#### 1. Vorschau ohne Hardware

```bash
.venv/bin/python -m drone_control run --mission examples/hover.toml
```

Ohne `--execute` öffnen `run` und `arm` keine Verbindung. Die Vorschau ist keine Simulation.

#### 2. Backpack verbinden und Telemetrie anzeigen

Sender und Empfänger müssen im ExpressLRS-MAVLink-Modus arbeiten. Am Sender **Backpack → Telemetry → WiFi** aktivieren und Laptop sowie Backpack mit demselben WLAN verbinden.

```bash
.venv/bin/python -m drone_control status --backpack
.venv/bin/python -m drone_control telemetry --backpack
```

`--backpack` verwendet `elrs_txbp.local`. Falls mDNS nicht funktioniert, die aktuelle Router-IP einsetzen:

```bash
.venv/bin/python -m drone_control telemetry --backpack 10.0.0.42
```

Die IP ist ein Beispiel. Die Webschnittstelle dient der Erkennung; MAVLink läuft anschließend über UDP. `Strg+C` beendet das Dashboard.

Weitere Verbindungsarten:

```bash
# Nur auf eingehende UDP-Telemetrie am Laptop lauschen
.venv/bin/python -m drone_control telemetry --connect udpin:0.0.0.0:14550

# Flugcontroller direkt per USB; Gerätename und Baudrate anpassen
.venv/bin/python -m drone_control telemetry --connect /dev/ttyACM0 --baud 115200
```

Der USB-Anschluss der Fernsteuerung mit HID/SD/VCP ist bei internen ELRS-Modulen allein keine bidirektionale MAVLink-Brücke. Für diesen Aufbau Backpack-WiFi verwenden; siehe [Verbindungsdetails](docs/usage.md#usb-menü-der-fernsteuerung-hid-sd-oder-vcp).

#### 3. Nur Armen testen

Bodentest **ohne Propeller**, nach dem Test per RC disarmen:

```bash
.venv/bin/python -m drone_control arm --backpack --execute
```

Der aktuelle Flugmodus bleibt erhalten. Das Programm sendet keinen Startbefehl und beendet sich nach bestätigtem Armen. Motoren können bereits beim Armen anlaufen. Automatisches Disarmen und Failsafes liegen beim FC.

#### 4. Flugablauf ausführen

Erst [FC-Voraussetzungen](#flugcontroller-vorbereiten) und [Testanleitung](docs/testing.md) durcharbeiten. Dashboard schließen, **GUIDED per RC wählen**, dann:

```bash
# Echter Flug: startet nach erfolgreichen Vorprüfungen unmittelbar
.venv/bin/python -m drone_control run --backpack --mission examples/hover.toml --execute
```

Bei Fehlern, Linkverlust oder `Strg+C` stellt das Programm Befehle und Missions-Heartbeats ein. Es sendet keinen nachträglichen LAND-Befehl hinter einer möglichen RC-Übernahme her. Der konfigurierte FC-Failsafe muss die Situation übernehmen; dessen Timeout bedeutet eine Verzögerung. Im normalen Ablauf wird LAND angefordert und auf das vom FC gemeldete Disarmen gewartet.

### Befehle und Optionen

| Befehl | Verhalten |
| --- | --- |
| `telemetry` | Live-Dashboard; fordert benötigte Telemetrie automatisch an |
| `status` | Einmaligen FC-Status ausgeben |
| `arm` | Arming-Vorschau; mit `--execute` tatsächlich armen |
| `run` | Missionsvorschau; mit `--execute` Mission ausführen |

| Option | Zweck / Standard |
| --- | --- |
| `--backpack [HOST]` | Backpack erkennen; ohne HOST: `elrs_txbp.local` |
| `--connect ENDPOINT` | Alternative zu `--backpack`; Standard: `udpin:0.0.0.0:14550` |
| `--baud BAUD` | Serielle Baudrate; `115200` |
| `--target-system ID` | MAVLink-System-ID des FC; `1` |
| `--source-system ID` | Eigene MAVLink-System-ID; `255` |
| `--mission PFAD` | TOML-Datei für `run`; `examples/hover.toml` |
| `--execute` | `arm` oder `run` tatsächlich ausführen |
| `--battery-profile PFAD` | Anzeigeprofil für `telemetry`; `battery.toml` |
| `--passive` | Bei `telemetry` keine UDP-Anmeldung oder MAVLink-Anfragen senden |
| `--help` | Hilfe mit weiteren Anwendungsbeispielen |

Bei `--backpack --passive` wird weiterhin die HTTP-Diagnose gelesen. Telemetrie sendet keine GCS-Heartbeats und keine Flugbefehle. Der frühere Schalter `--request-streams` wird noch akzeptiert, ist aber überflüssig.

### Missionen definieren

[examples/hover.toml](examples/hover.toml) enthält den unterstützten Ablauf. Eine eigene Datei kann diese Werte festlegen:

```toml
height_m = 0.5
hold_s = 5.0
takeoff_timeout_s = 30.0
landing_timeout_s = 60.0
```

| Feld | Bedeutung | Erlaubter Bereich |
| --- | --- | --- |
| `height_m` | Zielhöhe in Metern relativ zu Home | 0,3–3 |
| `hold_s` | Haltezeit in Sekunden | 0–120 |
| `takeoff_timeout_s` | Zeitlimit für den Start in Sekunden | 5–120 |
| `landing_timeout_s` | Zeitlimit für Landen/Disarmen in Sekunden | 10–180 |

Die TOML-Datei parametrisiert den festen Ablauf; sie enthält keine frei programmierbare Befehlsliste. Unbekannte Felder und ungültige Werte werden abgelehnt. Eigene Python-Abläufe können auf [mission.py](drone_control/mission.py) aufbauen.

### Flugcontroller vorbereiten

Das Programm schreibt keine gespeicherten FC-Parameter. Für `run --execute` prüft es unter anderem:

- disarmten Quadcopter am Boden und bereits gewählten GUIDED-Modus;
- frische Positions-, EKF- und Bodenkontaktmeldungen;
- aktivierte Arming-Prüfungen (`ARMING_CHECK != 0`) und RC-Failsafe (`FS_THR_ENABLE != 0`);
- GCS-Failsafe `FS_GCS_ENABLE = 5` (LAND), Timeout zwischen 2 und 10 Sekunden und passende GCS-System-ID;
- `LAND_SPEED` zwischen 10 und 30 cm/s.

Individuelle Arming-Bitmasken werden akzeptiert und protokolliert; ihre Eignung für den Einsatz bewertet das Programm nicht. Die Voraussetzungen für `arm` sind geringer als für einen Missionsflug. Details zu Sensorfusion, RC-Übernahme und Failsafes stehen in der [Betriebsanleitung](docs/usage.md#voraussetzungen-am-flugcontroller).

### Telemetrie und Akkuprofil

Das Dashboard verwendet Farben und passt sich der Terminalbreite an. Fehlende, ungültige oder über drei Sekunden alte Sensordaten erscheinen als `—`. Historische Arming-Hinweise und EKF-Umschaltmeldungen behalten ihr angegebenes Alter; sie bestätigen keinen aktuellen Zustand.

[battery.toml](battery.toml) enthält ein **Beispielprofil für Li-Ion 4S, 2500 mAh**. Für den eigenen Akku anpassen:

```toml
chemistry = "Li-Ion"
cells = 4
capacity_mah = 2500
```

Das Profil ergänzt den Zellmittelwert aus Packspannung/Zellenzahl. Es verändert weder FC-Prozentwerte noch Warnschwellen oder Failsafes. Die Akkufarbe richtet sich derzeit ausschließlich nach der FC-Restkapazität: über 30 % grün, 21–30 % gelb, bis 20 % rot; unvollständige Daten gelb. Die Spannung und die schwächste Einzelzelle werden damit nicht bewertet.

```bash
NO_COLOR=1 .venv/bin/python -m drone_control telemetry --backpack
```

Umgeleitete Ausgabe enthält automatisch keine Farben oder Bildschirmsteuerung. Erläuterungen zu GPS, Kompass, RC-RSSI, VTX und EKF-Quellensätzen stehen in der [Betriebsanleitung](docs/usage.md#laufende-telemetrieanzeige).

#### Akkudaten auf der Fernsteuerung ohne laufendes Programm

ExpressLRS benötigt `BATTERY_STATUS` für die EdgeTX-Sensoren RxBt, Curr, Capa und Bat%. Das Dashboard fordert diese Nachricht mit 1 Hz an. Für dauerhafte Übertragung unter ArduCopter 4.6.2 am passenden MAVLink-Anschluss **`SRx_EXTRA3 = 1`** speichern und den FC neu starten.

Die SR-Nummer entspricht nicht automatisch der UART-Nummer. In der erprobten Konfiguration mit USB, SERIAL4/MAVLink, SERIAL6/ELRS und SERIAL8/MAVLink ist **`SR2_EXTRA3 = 1`** richtig. Andere Portkonfigurationen benötigen eine erneute Zuordnung. Siehe [Anleitung zur dauerhaften Akkutelemetrie](docs/usage.md#akkudaten-dauerhaft-an-edgetx-senden).

### Fehlersuche

| Problem | Nächster Schritt |
| --- | --- |
| `elrs_txbp.local` nicht auflösbar | Aktuelle Router-IP hinter `--backpack` verwenden; mDNS prüfen |
| Backpack-Webseite erreichbar, aber Weiterleitung deaktiviert | Am Sender Telemetry auf Off und zurück auf WiFi stellen; Update-WiFi ist ein anderer Modus |
| Kein FC-Heartbeat | Drohnenversorgung, ELRS-Link, Telemetry/WiFi, UDP-Firewall und WLAN-Geräteisolierung prüfen; andere Bodenstationen schließen |
| UDP-Port bereits belegt | Vorhandenes Dashboard oder andere Bodenstation beenden |
| Armen abgelehnt | Die konkrete FC-Begründung im Log beheben; Prüfungen nicht pauschal deaktivieren |
| GPS-Fix vorhanden, aber keine Positionsfreigabe | EKF-Quellensatz, Origin/Home und Sensorfusion prüfen; 3D-Fix allein bestätigt keine Positionshaltung |
| Akkudaten nur am Laptop sichtbar | `BATTERY_STATUS` auf der ELRS-Verbindung bzw. die gespeicherte EXTRA3-Rate prüfen |
| Serieller Anschluss nicht zugänglich | Gerätenamen und `dialout`-Gruppenmitgliedschaft prüfen; nach Gruppenänderung neu anmelden |

### Entwicklung und Dokumentation

Tests ohne angeschlossene Drohne ausführen:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Die Tests prüfen unter anderem Missionsvalidierung, MAVLink-Verarbeitung, RC-Übernahme, Telemetrie und Backpack-Erkennung. Sie ersetzen keine SITL- und Hardwaretests.

| Datei / Verzeichnis | Inhalt |
| --- | --- |
| [drone_control/](drone_control/) | CLI, Verbindung, Missionslogik und Telemetrie |
| [examples/](examples/) | Beispielmissionen |
| [tests/](tests/) | Unit-Tests |
| [docs/usage.md](docs/usage.md) | Ausführliche Betriebs- und Schnittstellenerklärungen |
| [docs/testing.md](docs/testing.md) | Testablauf und SITL-Hinweise |
| [docs/gps-test.md](docs/gps-test.md) | Lesende UBX-Diagnose über USB-Passthrough |

Bei der Entwicklung von Code und Dokumentation wurde **OpenAI Codex CLI** eingesetzt.

Quellcode, Tests und TOML-Konfigurationen enthalten Header mit Funktion, Projektversion, Header-Datum, Mitwirkenden, Codex-CLI-Unterstützung und Apache-2.0-Lizenz. Die Versionsangabe entspricht der Paketversion in `pyproject.toml` und wird bei einer neuen Projektversion gemeinsam aktualisiert. Das Header-Datum bezeichnet die Ergänzung des Headers, nicht das Erstellungsdatum der Datei.

Fehlerberichte sollten den verwendeten Befehl, die Fehlermeldung, Python-/ArduCopter-/ELRS-/Backpack-Versionen und den Verbindungsweg enthalten. Standortkoordinaten und WLAN-Zugangsdaten vor Veröffentlichung entfernen. Änderungen bitte mit nachvollziehbarer Beschreibung und passenden Tests einreichen.

Weitere Referenzen: [ArduPilot GUIDED](https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html), [GCS-Failsafe](https://ardupilot.org/copter/docs/gcs-failsafe.html), [ExpressLRS MAVLink](https://www.expresslrs.org/software/mavlink/).

### Lizenz

Dieses Projekt steht unter der **Apache License, Version 2.0**. Der vollständige Lizenztext steht in [LICENSE](LICENSE). Abhängigkeiten unterliegen ihren jeweiligen eigenen Lizenzen.
