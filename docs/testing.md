# Prüfablauf

## ArduPilot SITL

SITL nach der offiziellen [ArduPilot-Anleitung](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html) separat installieren. Beispiel im ArduPilot-Checkout:

```bash
Tools/autotest/sim_vehicle.py -v ArduCopter -f quad --console --map
```

In der MAVProxy-Konsole eine eigene Verbindung hinzufügen und Testparameter setzen:

```text
output add 127.0.0.1:14560
param set FS_GCS_ENABLE 5
param set FS_GCS_TIMEOUT 5
param set LAND_SPEED 20
param set ARMING_CHECK 1
mode guided
```

Die vom Projekt geprüfte GCS-ID passend zu 255 einstellen (`SYSID_MYGCS` oder `MAV_GCS_SYSID`, je nach Firmware). Bei GPS-SITL abwarten, bis Position und Prearm-Checks bereit sind. Im Projekt:

```bash
.venv/bin/python -m drone_control run --connect udpin:127.0.0.1:14560 --execute
```

Erwartung: Scharfschaltung, Start, Halten, LAND, automatisches Disarmen. 0,5-m-Ziel auf tatsächliches Verhalten prüfen. SITL mit GPS prüft den Ablauf, nicht die physikalischen Eigenschaften des MTF-01P.

Weitere Szenarien separat durchführen:

- Während Start und Halten in MAVProxy `mode althold` setzen. Der Ablauf muss abbrechen und darf keinen LAND-Befehl mehr senden.
- Beim Start deaktivierte Failsafe- oder unpassende Landegeschwindigkeitsparameter setzen: Abbruch vor Armen.
- Programm während GUIDED beenden: FC muss nach dem GCS-Timeout reagieren. MAVProxy sendet selbst GCS-Heartbeats; diese können denselben System-ID-Watchdog weiter bedienen! Für diesen Versuch andere Heartbeat-Sender entfernen oder nachweislich verschiedene, nicht akzeptierte GCS-IDs verwenden. Ausbleibender Failsafe ist kein bestandener Test.
- Telemetrie aussetzen: der Computer muss abbrechen. Diesen Test zuerst ausschließlich in Simulation durchführen.

## Hardware

Ohne Propeller Rückkanal, Parameterauslesen, Modusschalter und Funkverlust prüfen. Danach Positionshaltung mit dem MTF-01P per RC nachweisen. Erst anschließend den echten Ablauf testen. Eine Simulation kann Funklatenz, Bodenstruktur, Licht, Bodeneffekt oder fehlerhafte Sensororientierung nicht validieren.
