# SPDX-License-Identifier: Apache-2.0
"""Parse CLI options and dispatch telemetry, status, arming, and mission commands.

File: drone_control/cli.py
Project: drone_control
Version: 0.1.0 (project version)
Header added: 2026-11-17
Authors: drone_control contributors
Development assistance: OpenAI Codex CLI
License: Apache License, Version 2.0; see LICENSE in the repository root.
"""

import argparse
import logging
from .mission import Mission, fly


def main():
    parser = argparse.ArgumentParser(
        description="ArduCopter über MAVLink: Telemetrie anzeigen und einfache Flugabläufe ausführen.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Befehle:
  telemetry  Laufendes Dashboard; fragt Telemetriedaten automatisch an.
  status     FC-Status einmal ausgeben und beenden.
  run        Ohne --execute nur Vorschau, ohne Verbindung zur Drohne.
  arm        Nur armen, kein Abheben; ohne --execute nur Vorschau.

Anwendungsbeispiele (im Projektverzeichnis ausführen):

  Dashboard im Heim-WLAN, z. B. Olymp:
    .venv/bin/python -m drone_control telemetry --backpack

  Backpack über seine IP erreichen, falls elrs_txbp.local nicht auflösbar ist:
    .venv/bin/python -m drone_control telemetry --backpack 10.0.0.42
    (Beispiel-IP durch die Adresse aus deinem Router ersetzen.)

  Verbindung zum Backpack und FC kurz prüfen:
    .venv/bin/python -m drone_control status --backpack

  Direkt mit dem Backpack-WLAN verbunden: lokal auf UDP 14550 lauschen:
    .venv/bin/python -m drone_control telemetry

  Flugcontroller direkt per USB anschließen:
    .venv/bin/python -m drone_control telemetry --connect /dev/ttyACM0 --baud 115200
    (Gerätenamen anpassen; gemeint ist USB am FC, nicht an der Fernsteuerung.)

  Ausschließlich eingehende Telemetrie anzeigen, ohne Datenanfragen:
    .venv/bin/python -m drone_control telemetry --passive

  Ein anderes lokales Akku-Anzeigeprofil verwenden:
    .venv/bin/python -m drone_control telemetry --backpack --battery-profile battery.toml

  Dashboard ohne Farben:
    NO_COLOR=1 .venv/bin/python -m drone_control telemetry --backpack

  Flugablauf nur als Vorschau ansehen (keine Verbindung, kein Armen):
    .venv/bin/python -m drone_control run --mission examples/hover.toml

  Nur Armen als Vorschau (keine Verbindung):
    .venv/bin/python -m drone_control arm

  Nur tatsächlich armen, keinen Startbefehl senden (Bodentest ohne Propeller):
    .venv/bin/python -m drone_control arm --backpack --execute
    Der Flugmodus bleibt erhalten. Danach per RC wieder disarmen.

  ECHTER FLUG: Ablauf nach erfolgreichen Vorprüfungen unmittelbar starten:
    .venv/bin/python -m drone_control run --backpack --mission examples/hover.toml --execute
    Vorher GUIDED per RC wählen und Voraussetzungen in README.md prüfen.
    Zur RC-Übernahme in einen anderen Flugmodus schalten.

Hinweise:
  --backpack und --connect sind Alternativen und nicht kombinierbar.
  Im ELRS-Menü muss Backpack → Telemetry → WiFi aktiv sein. Bei erreichbarer
  Weboberfläche, aber deaktivierter Weiterleitung: Off und zurück auf WiFi.
  Höhe und Haltezeit stehen in der Missionsdatei, nicht in CLI-Optionen.
  --battery-profile ändert nur die Anzeige, keine ArduPilot-Parameter.
  Strg+C beendet die Anzeige. Details und Testablauf stehen in README.md.
""")
    parser.add_argument("action", choices=["run", "arm", "status", "telemetry"],
                        help="Flugablauf/Vorschau, nur Armen, einmaliger Status oder Live-Dashboard")
    parser.add_argument("--mission", default="examples/hover.toml",
                        help="TOML-Flugablauf für run (Standard: examples/hover.toml)")
    connection = parser.add_mutually_exclusive_group()
    connection.add_argument("--backpack", nargs="?", const="elrs_txbp.local",
                            help="Backpack im Heim-WLAN über Host/IP erkennen (Standardhost: elrs_txbp.local)")
    connection.add_argument("--connect", default=None,
                        help="Backpack: udpin:0.0.0.0:14550 (Standard); USB direkt am FC/externen TX: /dev/ttyACM0. "
                             "USB-VCP der Fernsteuerung allein ist keine MAVLink-Brücke.")
    parser.add_argument("--battery-profile", default="battery.toml",
                        help="Lokales Akku-Anzeigeprofil für telemetry (Standard: battery.toml)")
    parser.add_argument("--baud", type=int, default=115200, help="Serielle Baudrate (Standard: 115200)")
    parser.add_argument("--target-system", type=int, default=1, help="MAVLink-System-ID des FC (Standard: 1)")
    parser.add_argument("--source-system", type=int, default=255, help="Eigene MAVLink-System-ID (Standard: 255)")
    parser.add_argument("--execute", action="store_true", help="run oder arm tatsächlich ausführen (sonst Vorschau)")
    streams = parser.add_mutually_exclusive_group()
    streams.add_argument("--passive", action="store_true",
                         help="Bei telemetry: nur empfangen, keine Telemetriedaten anfragen")
    streams.add_argument("--request-streams", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (args.request_streams or args.passive) and args.action != "telemetry":
        parser.error("--passive/--request-streams sind nur für telemetry vorgesehen")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    vehicle = None
    try:
        if not 1 <= args.target_system <= 255 or not 1 <= args.source_system <= 255:
            raise ValueError("System-IDs müssen zwischen 1 und 255 liegen")
        if args.target_system == args.source_system:
            raise ValueError("FC und GCS benötigen verschiedene System-IDs")
        if args.action == "arm" and not args.execute:
            print("VORSCHAU: nur normal armen, kein Abheben, kein Moduswechsel. Keine Verbindung geöffnet.")
            return 0
        mission = Mission.load(args.mission) if args.action == "run" else None
        if args.action == "run" and not args.execute:
            print(f"VORSCHAU: armen → {mission.height_m:.2f} m relativ zu Home → "
                  f"{mission.hold_s:.1f} s halten → LAND. Keine Verbindung geöffnet.")
            return 0
        battery_profile = None
        if args.action == "telemetry":
            from .battery import BatteryProfile
            from pathlib import Path
            if Path(args.battery_profile).is_file():
                battery_profile = BatteryProfile.load(args.battery_profile)
            elif args.battery_profile != "battery.toml":
                raise ValueError(f"Akku-Anzeigeprofil fehlt: {args.battery_profile}")
        from .vehicle import Vehicle
        peer = None
        endpoint = args.connect or "udpin:0.0.0.0:14550"
        if args.backpack:
            from .backpack import discover
            ip, remote_port, local_port = discover(args.backpack)
            endpoint = f"udpin:0.0.0.0:{local_port}"
            peer = (ip, remote_port)
            logging.info("Backpack %s: Ziel UDP %s, lokaler Empfang UDP %s", ip, remote_port, local_port)
        if endpoint.startswith("udpin:"):
            local_host, local_port = endpoint.removeprefix("udpin:").rsplit(":", 1)
            interfaces = "allen lokalen IPv4-Schnittstellen" if local_host == "0.0.0.0" else local_host
            logging.info("Lausche am Laptop auf UDP-Port %s (%s)", local_port, interfaces)
            if peer is None:
                logging.info("Warte auf eingehende MAVLink-Daten; für gezielte Backpack-Erkennung --backpack verwenden")
        else:
            logging.info("Öffne MAVLink-Verbindung: %s", endpoint)
        vehicle = Vehicle(endpoint, args.baud, args.target_system, args.source_system)
        if peer and not args.passive:
            vehicle.register_backpack(peer)
        logging.info("Warte bis zu 15 Sekunden auf den Flugcontroller (System %s) …", args.target_system)
        vehicle.connect()
        if args.action == "status":
            beat = vehicle.fresh("HEARTBEAT")
            print(f"System {args.target_system}: Modus-ID {beat.custom_mode}, "
                  f"base_mode={beat.base_mode}, Status={beat.system_status}")
            return 0
        if args.action == "telemetry":
            from .telemetry import watch
            watch(vehicle, request_streams=not args.passive, battery_profile=battery_profile)
            return 0
        if args.action == "arm":
            vehicle.arm_only()
            return 0
        fly(vehicle, mission)
        return 0
    except KeyboardInterrupt:
        if args.action not in ("run", "arm"):
            print("\nAnzeige beendet.")
            return 0
        logging.error("Abgebrochen: keine weiteren Befehle/Heartbeats. RC übernehmen; FC-Failsafe beachten.")
        return 130
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        if args.action not in ("run", "arm") or not args.execute:
            logging.error("%s", error)
        else:
            logging.error("%s. Keine weiteren Befehle/Heartbeats; RC bzw. FC-Failsafe übernimmt.", error)
        return 1
    finally:
        if vehicle is not None:
            vehicle.close()
