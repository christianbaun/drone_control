# GPS-Rückkanal über UBX-MON-VER prüfen

Das Diagnosewerkzeug sendet nur eine UBX-Versionsabfrage (Klasse 0x0A, ID 0x04, leere Nutzdaten). Es schreibt keine GPS-Konfiguration und sendet keine MAVLink-/Arming-Befehle. Voraussetzung ist ein zuvor eingerichteter USB-Passthrough. Es aktiviert diesen nicht selbst.

## Vorbereitung für MicoAir743v2 mit GPS an SERIAL3

1. Propeller abnehmen, FC disarmt lassen. Die Bodenstation und das GPS müssen ausreichend versorgt sein. Nicht armen oder fliegen, solange Passthrough aktiv ist.
2. FC direkt per USB am Debian-Rechner anschließen. `drone_control`-Telemetrie beenden. MicoConfigurator verbinden.
3. Die bisherigen Werte von `SERIAL3_BAUD`, `SERIAL_PASS1`, `SERIAL_PASS2` und `SERIAL_PASSTIMO` notieren.
4. Die tatsächlich benutzte GPS-Baudrate ermitteln. ArduPilot kann das GPS bei der Erkennung auf 230400 umstellen, auch wenn `SERIAL3_BAUD` zuvor 115200 enthielt. Für Passthrough muss dieser Parameter zur tatsächlichen GPS-Baudrate passen. Im Zweifel zunächst 230400 versuchen: Parameterwert `SERIAL3_BAUD=230`. Nur den Parameter auf 115200 zu ändern bedeutet nicht automatisch, dass das GPS nun selbst mit 115200 arbeitet.
5. In der vollständigen Parameteransicht zuerst `SERIAL_PASS1=0` (primärer USB-Port) und `SERIAL_PASSTIMO=60` setzen. **Zuletzt** `SERIAL_PASS2=3` schreiben.
6. MicoConfigurator sofort trennen/schließen, USB-Kabel angeschlossen lassen. Nicht neu starten. Die MAVLink-Verbindung wird während Passthrough unterbrochen; das ist erwartet. Innerhalb der Timeout-Zeit den Test starten.

## Abfrage unter Debian

USB-Gerät ermitteln, möglichst vor Aktivierung des Passthrough:

```bash
.venv/bin/python -m serial.tools.list_ports -v
```

Den gleichen USB-Port verwenden, über den MicoConfigurator verbunden war; ggf. `/dev/ttyACM0` ersetzen:

```bash
.venv/bin/python -m drone_control.gps_probe --port /dev/ttyACM0 --baud 230400
```

Falls das GPS tatsächlich 115200 verwendet: `SERIAL3_BAUD=115` einstellen, Passthrough wie oben neu aktivieren und mit `--baud 115200` testen. Ein Wechsel allein am Python-Aufruf stellt den GPS-UART nicht zuverlässig um.

Der Test sendet bis zu drei Anfragen und wartet jeweils drei Sekunden. Antworten werden als vollständige UBX-Pakete mit passender Klasse/ID, Länge und korrekter Prüfsumme geprüft. Zufällige Bytes oder bloße Positionsmeldungen zählen nicht als Erfolg. Ein Empfang nach unserer Anfrage ist ein starker Hinweis auf den funktionierenden Rückkanal; UBX hat hierfür keine Transaktions-ID. Anderweitig ausgelöste, gleichzeitig übertragene Versionsantworten lassen sich daher nicht absolut ausschließen.

## Ergebnis

- **Gültige MON-VER-Antwort:** Software-/Hardwarekennung ausgeben und zur weiteren Diagnose mitteilen. Ein funktionierender Rückkanal beweist noch nicht, dass B101 alle Konfigurationsbefehle von ArduPilot unterstützt.
- **Gültige UBX-Pakete, aber keine MON-VER-Antwort:** Empfang funktioniert; Rückleitung oder Befehlsunterstützung sind weiterhin offen.
- **Keine Daten/Prüfsummenfehler:** Passthrough, Port, Versorgung und Baudrate kontrollieren. Das ist kein eindeutiger Kabeldefekt-Nachweis.

## Danach zurück zum Normalbetrieb

Test beenden und FC neu starten. Wenn MicoConfigurator wieder verbunden ist, `SERIAL_PASS2=-1` prüfen, `SERIAL_PASS1`/`SERIAL_PASSTIMO` sowie gegebenenfalls die Baudrate auf die notierten Einstellungen zurücksetzen. Das Timeout ist nur eine Hilfestellung; vor normalem Betrieb den beendeten Passthrough ausdrücklich kontrollieren. `GPS_AUTO_CONFIG` und `ARMING_CHECK` bleiben unverändert.

Quellen: [ArduPilot Serial Passthrough](https://ardupilot.org/copter/docs/common-serial-passthrough.html), [MON-VER-Abfrage im ArduPilot-4.6.2-Treiber](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.2/libraries/AP_GPS/AP_GPS_UBLOX.cpp).

## Zusätzlich: GPS-Messrate nur auslesen

Bei offener „navigation rate configuration“ kann im gleichen vorbereiteten Passthrough gezielt die ältere UBX-CFG-RATE-Abfrage des ArduPilot-4.6.2-Treibers getestet werden:

```bash
.venv/bin/python -m drone_control.gps_probe --port /dev/ttyACM0 --baud 230400 --query rate
```

Die leere Poll-Anfrage schreibt keine Messrate. Eine Antwort zeigt Messintervall, Navigationszyklen und Zeitreferenz. Für `GPS1_RATE_MS=200` erwartet der 4.6.2-Treiber die Werte 200 ms, 1 und 0 (UTC). Ein ausdrücklich passendes ACK-NAK zeigt eine Ablehnung dieser Anfrage, nicht eine unterbrochene Leitung. Keine Antwort ist weiterhin mehrdeutig. Die Prüfung auf Zielwerte verändert den GPS-Zustand nicht. Danach Passthrough wie oben beenden.

## M10 SPG 5.10: moderne Abfrage über CFG-VALGET

Wenn MON-VER beantwortet wird und die ältere CFG-RATE-Abfrage trotz gültigem UBX-Empfang ohne Antwort bleibt, lässt sich stattdessen das aktive Messintervall über die Konfigurationsdatenbank auslesen:

```bash
.venv/bin/python -m drone_control.gps_probe --port /dev/ttyACM0 --baud 230400 --query rate-modern
```

Das Werkzeug fragt ausschließlich den Schlüssel `CFG-RATE-MEAS` (`0x30210001`, U2) aus Layer RAM ab. Es sendet keinen VALSET- oder VALDEL-Befehl. Der passende Antwortschlüssel, Layer, Antwortversion, Paketlänge und Prüfsumme werden geprüft. Auch hierfür muss der USB-Passthrough aktiv sein. Quelle: [u-blox M10 SPG 5.10, Protokoll 34.10, CFG-VALGET und CFG-RATE-Konfigurationsschlüssel](https://content.u-blox.com/sites/default/files/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf). Eine erfolgreiche moderne Abfrage allein beweist noch nicht, welcher Teil der automatischen FC-Konfiguration hängen bleibt.

## Prüfen, ob MON-VER ungefragt gesendet wird

Bei aktiver USB-Brücke zunächst ohne jede Anfrage sechs Sekunden zuhören:

```bash
.venv/bin/python -m drone_control.gps_probe --port /dev/ttyACM0 --baud 230400 --query listen
```

Dieser Modus führt keine seriellen Schreibzugriffe aus. Er zählt Nachrichtentypen und kennzeichnet MON-VER, falls diese ohne Anfrage erscheinen. Dann ist ein erfolgreicher vorheriger Versionstest allein kein belastbarer Rückkanalnachweis. Auch ohne ungefragte Version im kurzen Mitschnitt ist deren spätere Antwort kein absoluter Beweis. Bei ausbleibenden Konfigurationsantworten nicht allein deswegen eine Firmware-Inkompatibilität behaupten. Die aktiven Abfragen zeigen bei Zeitüberschreitung ebenfalls die empfangenen Nachrichtentypen; Antworten mit unerwarteter Nutzdatenstruktur werden zusätzlich als Hexdaten angegeben.

## Bestätigungen einordnen

Das Werkzeug zeigt bei ACK-ACK und ACK-NAK die bestätigte Klasse/ID und Nutzdaten. Für `rate-modern` muss eine zugehörige Bestätigung `06/8B` enthalten. Eine solche Bestätigung zeigt eine Reaktion auf diese Befehlskennung; sie ersetzt nicht die erwartete CFG-VALGET-Antwort mit Schlüsseln und Werten. Fremde ACKs zählen nicht als Antwort. Falls der Test von einem parallel aktiven GPS-Treiber beeinflusst sein könnte, lässt sich dieser nur für den disarmten USB-Bodentest mit `GPS1_TYPE=0` und anschließendem Neustart deaktivieren. Vor normalem Betrieb `GPS1_TYPE=1`, `SERIAL_PASS2=-1` wiederherstellen und neu starten. Das ist keine Lösung der ursprünglichen Arming-Sperre und keine Aufforderung, ohne GPS-Treiber zu fliegen.
