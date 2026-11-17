# Ausführliche Betriebsanleitung

Kleines Python-Projekt für ArduCopter auf dem MicoAir743 V2: armen, auf eine konfigurierte Höhe steigen, Position halten und mit LAND landen. Die Laufzeitabhängigkeiten sind `pymavlink` und `pyserial`. ArduPilot übernimmt Stabilisierung, EKF und die Motorregelung. Der MTF-01P bleibt direkt am Flugcontroller angeschlossen.

## Installation

Python ab 3.11 (Debian 12 oder neuer):

```bash
sudo apt install python3 python3-venv
python3 -m venv .venv
.venv/bin/pip install -e .
```

Alle folgenden Befehle im Projektverzeichnis ausführen. Die TOML-Dateien sind einfach editierbare Autopilotskripte. Eigene Python-Abläufe können die Methoden in `drone_control/mission.py` verwenden.

## Ohne Drohne ausprobieren

```bash
.venv/bin/python -m drone_control run --mission examples/hover.toml
.venv/bin/python -m unittest discover -s tests -v
```

Ohne `--execute` zeigt `run` ausschließlich den Ablauf und öffnet keine Verbindung. Das ist eine Vorschau, keine Flugsimulation.

## Laufende Telemetrieanzeige

```bash
.venv/bin/python -m drone_control telemetry --connect udpin:0.0.0.0:14550
```

Das lokale Anzeigeprofil [battery.toml](../battery.toml) ist auf deinen **Li-Ion 4S 2500 mAh** eingestellt. `telemetry` lädt es aus dem aktuellen Projektverzeichnis; mit `--battery-profile PFAD` kann ein anderes Profil ausgewählt werden. Fehlt die Standarddatei, bleibt die bisherige Anzeige ohne Profil aktiv. Akkutyp, Zellenzahl und Kapazität sind editierbar. Die Anzeige ergänzt den rechnerischen Zellmittelwert (Packspannung / Zellenzahl), beispielsweise **15,40 V / 4 = 3,85 V/Zelle**. Das ist keine Messung der schwächsten Einzelzelle.

Das Profil ändert weder die vom FC gelieferten Prozente noch FC-Parameter oder Failsafes. Für die FC-Restkapazitätsschätzung sollte `BATT_CAPACITY` zur tatsächlichen Kapazität von 2500 mAh passen und der Spannungs-/Strommonitor kalibriert sein. Die Spannung allein ergibt keinen verlässlichen Prozentwert; auch ein teilgeladener Akku beim Einschalten kann eine hohe FC-Schätzung liefern. Siehe [ArduPilot-Batteriemonitor](https://ardupilot.org/copter/docs/common-power-module-configuration-in-mission-planner.html). Spannungsschwellen müssen zum konkreten Zellentyp und Betrieb passen; das Anzeigeprofil setzt deshalb keine zusätzlichen pauschalen Li-Ion-Spannungsgrenzen.

Der Akku steht direkt unter dem Titel mit Spannung, Strom und der vom FC geschätzten Restkapazität. Die Hervorhebung richtet sich ausschließlich nach dieser Schätzung: über 30 % grün (bei vollständigen Daten), 21–30 % gelb, bis 20 % weiß auf rotem Hintergrund. Fehlende oder veraltete Daten erscheinen gelb. Diese UI-Schwellen sind keine Akku- oder Failsafe-Konfiguration; Zellenzahl, Chemie, Spannungseinbruch und die Kalibrierung des Batteriemonitors werden damit nicht bewertet.

Die Anzeige verwendet ein farbiges Dashboard mit Bereichen für Flug/Höhe, GPS/Orientierung, Sensoren/Batterie und EKF/Quellen. Ab 120 Terminalspalten erscheinen zwei Spalten. Grün markiert Verbindung bzw. vom FC gemeldete Gesundheit, Gelb fehlende Werte oder scharfgeschaltete Motoren, Rot Warnungen wie `GPS_GLITCHING` und Verbindungsabbruch. Farben sind keine Flugfreigabe. Auf kleinen Terminals werden Details mit einem Hinweis gekürzt; Warnungen bleiben oben. Für alle Details das Terminal vergrößern oder die Ausgabe in eine Datei umleiten. Bei normalem Beenden wird die ursprüngliche Terminalansicht samt Cursor wiederhergestellt.

Mit `NO_COLOR=1 .venv/bin/python -m drone_control telemetry` lassen sich Farben deaktivieren. Umgeleitete Ausgabe enthält automatisch weder Farben noch Bildschirmsteuerung.

Die Anzeige aktualisiert sich im Terminal zweimal pro Sekunde; `Strg+C` beendet sie. In Dateien umgeleitete Ausgabe erzeugt alle zwei Sekunden einen neuen Textblock. Angezeigt werden:

- Flugmodus, Armed-/Disarmed-Zustand und frischer Heartbeat;
- Höhe relativ zu Home und separat der nach unten gemessene Sensorabstand;
- Roll (seitliche Neigung), Pitch (Längsneigung), Yaw (Gierwinkel) in Grad;
- horizontale Geschwindigkeit und vertikale Steiggeschwindigkeit in m/s;
- GPS-Breite/Länge (WGS84), GPS-Höhe über dem mittleren Meeresspiegel (MSL), Fix-Typ, Satellitenzahl, HDOP/VDOP und gemeldete horizontale Genauigkeit;
- Ausrichtung der Drohne als Gradwert von 0 bis 360 und Himmelsrichtung (N/NO/O/SO/S/SW/W/NW), getrennt vom GPS-Bewegungskurs;
- Magnetometerstatus laut FC sowie Magnetfeld X/Y/Z und Betrag aus `SCALED_IMU`, sofern geliefert;
- Batteriespannung, Strom und Restkapazität, soweit der FC diese liefert;
- zuletzt gemeldeter EKF3-Quellensatz und lesbare EKF-Warnungen (GPS unplausibel, Filter nicht initialisiert, Konstantpositionsmodus). „Keine Warnflags gemeldet“ bedeutet keine dieser gemeldeten Warnungen, keine Flugfreigabe.

Die Anzeige unterscheidet EKF3-Quellensätze 1/2/3 (`EK3_SRC1_*` bis `EK3_SRC3_*`). Den statischen Filtertyp und die numerische Statusbitmaske blendet sie aus.

Die GPS-Position stammt aus `GPS_RAW_INT` (erst ab 2D-Fix), nicht aus der EKF-Positionsschätzung. GPS-Höhe wird erst ab 3D-Fix angezeigt und ist eine andere Referenz als die Home-Höhe. HDOP/VDOP sind dimensionslose Geometriewerte, keine Genauigkeit in Metern. Eine horizontale Genauigkeit in Metern erscheint nur, wenn das GPS-Erweiterungsfeld `h_acc` gesetzt ist. Ohne GPS-Fix werden eventuell noch übertragene alte Koordinaten ausgeblendet.

Die Ausrichtung stammt aus `GLOBAL_POSITION_INT.hdg`, ersatzweise aus `ATTITUDE.yaw`. Sie beschreibt die geschätzte Richtung der Fahrzeugnase, nicht eine direkt aus Magnetometer-Rohwerten berechnete Kompassrichtung. Bei deinen Quellensätzen mit `YAW=1` trägt der Kompass zur Schätzung bei. Die Nordreferenz hängt von der korrekten ArduPilot-Konfiguration einschließlich Deklination ab. GPS-Bewegungskurs beschreibt dagegen die Bewegungsrichtung und ist im Stillstand keine verlässliche Orientierung.

Magnetfeldwerte werden in Milligauss (mG) aus `SCALED_IMU` angezeigt; Nullvektoren erscheinen als unbekannt. Der FC-Gesundheitsstatus ist eine separate Diagnose und kein Kalibrierungsnachweis. `SCALED_IMU` bezeichnet den gemeldeten Sensor, nicht automatisch einen bestimmten externen Kompass im GPS-Modul. Andere Kompassinstanzen werden hier nicht einzeln angefordert. Die Anzeige fragt GPS und `SCALED_IMU` zusätzlich mit jeweils 1 Hz an. Falls die Firmware diese Nachricht nicht liefert, bleibt das Magnetfeld unbekannt. Felddefinitionen: [MAVLink GPS_RAW_INT](https://mavlink.io/en/messages/common.html#GPS_RAW_INT) und [SCALED_IMU](https://mavlink.io/en/messages/common.html#SCALED_IMU).

`—` bedeutet: noch nicht empfangen, älter als drei Sekunden oder ungültig. Bei Verbindungsverlust läuft die Anzeige weiter, markiert die fehlende Verbindung und wartet auf neue Daten. Die Anzeigeaktualisierung ist unabhängig von der tatsächlichen Sensordatenrate über ELRS.

Standardmäßig fragt `telemetry` beim Start die benötigten Daten mit niedrigen Raten (1–2 Hz) an. Dafür ist kein zusätzlicher Schalter nötig:

```bash
.venv/bin/python -m drone_control telemetry
```

Die Anzeige sendet dabei keine Flugbefehle und keine GCS-Heartbeats. Sie armt nicht und ändert keine Flugmodi oder gespeicherten Parameter. Mit `telemetry --passive` empfängt sie ausschließlich, etwa wenn eine andere Bodenstation die Datenraten vorgibt oder für Diagnosezwecke. Das bisherige `--request-streams` wird aus Kompatibilitätsgründen weiterhin akzeptiert, ist aber überflüssig. Die tatsächlichen Raten hängen von Firmware, Funkbandbreite und anderen Bodenstationen ab; nicht unterstützte oder abgelehnte Anfragen bleiben als fehlende Werte sichtbar. Die Anzeige ist damit keine GCS-Heartbeat-Quelle für den Flug-Failsafe. Für einen anschließenden Flugablauf zuerst die Anzeige beenden, damit nur ein Programm den UDP-Port verwendet.

Eine zusätzliche Abstand-Diagnose unterscheidet fehlende/veraltete Nachrichten, andere Sensororientierungen und ungültige Messwerte. Signalqualität 0 bedeutet unbekannt und blendet einen sonst gültigen Abstand nicht aus; Signalqualität 1 bedeutet ungültig.

### RC-Funkstrecke und iFlight Blitz VTX

Die Anzeige fragt `RC_CHANNELS` mit 1 Hz an und nutzt dessen RSSI-Feld als **normierten FC-RSSI-Indikator** (0–254 auf 0–100 %). Das ist weder ein dBm-Wert noch eine gemessene ELRS-Paket-Linkqualität (LQ). Was der FC als RSSI liefert, hängt von Empfänger und `RSSI_TYPE` ab. Die [ExpressLRS-MAVLink-Anleitung](https://www.expresslrs.org/software/mavlink/#flight-controller-setup) nennt `RSSI_TYPE=5`; das Programm verändert diesen Parameter nicht. 255, fehlende und veraltete Nachrichten ergeben `—`. Es gibt keine allgemeingültigen farbigen Reichweitenschwellen für diesen Indikator. Die zuvor entfernte RC8-PWM-Zeile bleibt ausgeblendet.

Falls `RADIO_STATUS` eintrifft, erscheinen die lokale/ferne Signalstärke auf ihrer gerätespezifischen Skala, der freie Sendepuffer und Empfangsfehlerzähler. Die System-/Komponenten-ID steht dabei. Nachrichten vom gewählten Fahrzeugsystem sowie von Radio-Komponente 68 werden dafür angenommen, auch wenn das Modul eine eigene System-ID verwendet. Andere Flugzustände werden weiterhin ausschließlich vom Ziel-FC ausgewertet. Nur einen Funklink pro Verbindung verwenden. Diese Werte werden nicht ohne bekannte Firmware-Zuordnung als ELRS-Uplink-/Downlink-LQ oder dBm bezeichnet; WLAN-Signal am Laptop wird nicht als RC-Funkqualität ausgegeben. [RADIO_STATUS-Felder](https://mavlink.io/en/messages/common.html#RADIO_STATUS)

Für den **iFlight Blitz via IRC Tramp an UART2** liest das Programm `VTX_ENABLE`, `VTX_FREQ`, `VTX_BAND`, `VTX_CHANNEL`, `VTX_POWER` und `VTX_OPTIONS` einzeln aus. Die Abfrage wird etwa alle 22 Sekunden wiederholt, Werte älter als 35 Sekunden werden ausgeblendet. Angezeigt werden Frequenz in MHz, Band, Kanal (benutzerfreundlich 1–8 statt FC-Index 0–7), Leistung in mW und das Pit-Mode-Bit. Es handelt sich um **FC-Einstellungen**, nicht um einen unabhängigen Nachweis der tatsächlichen HF-Leistung oder eines funktionierenden Videosignals. Bei fehlenden Antworten erscheint `—`, bei `VTX_ENABLE=0` ein entsprechender Hinweis. Bei aktivem PIT-Modus wird „Pit-Mode (FC): AN“ cyan hervorgehoben. Die Leistungszeile zeigt dann „PIT (mW unbekannt; normal: 25 mW)“ mit der jeweils konfigurierten Normalleistung. Die tatsächliche PIT-Leistung wird nicht übermittelt; sie wird deshalb nicht als 0 mW oder als Normalleistung ausgegeben. Bei fehlendem/veraltetem PIT-Status bleibt die Leistung unbekannt, die Normalleistung wird separat beschriftet. Es werden keine Einstellungen geschrieben; `--passive` sendet auch diese Anfragen nicht.

Voraussetzung ist bereits funktionierende Tramp-Anbindung am FC. ArduPilot dokumentiert `VTX_ENABLE=1` und für den zugehörigen seriellen Anschluss Protokoll 44 (IRC Tramp). „UART2“ muss dabei anhand der Board-Zuordnung dem richtigen `SERIALx` entsprechen; nicht allein wegen des Namens blind `SERIAL2` ändern. Siehe [ArduPilot Video Transmitter Support](https://ardupilot.org/copter/docs/common-vtx.html). Das Programm fordert keine VTX-Temperatur an, weil dafür hier keine bestätigte MAVLink-Quelle vorliegt.

### EKF Source Set über Kanal 8

Für deine Konfiguration `RC8_OPTION=90` zeigt die Anzeige die letzte empfangene FC-Meldung `Using EKF Source Set 1/2/3` mit Alter. Niedrige/mittlere/hohe Schalterstellung fordert Quellensatz 1/2/3 an. Das Programm verändert weder Kanal 8 noch den Quellensatz.

Die Profilbeschriftungen entsprechen deinen angegebenen Einstellungen: Set 1 = GPS/Barometer, Set 2 = Optical Flow/Barometer, Set 3 = Optical Flow/Entfernungssensor. Sie werden nicht aus den `EK3_SRC*`-Parametern ausgelesen. Set 2 bedeutet „Barometer als vertikale Positionsquelle“, nicht grundsätzlich „kein Entfernungssensor“: Optical Flow benötigt eine Entfernungsschätzung zur Skalierung.

Die Umschaltmeldung ist ein Ereignis, keine laufende Zustandsbestätigung. Nach Programmstart ohne empfangene Meldung bleibt das Set unbekannt; ohne Propeller den RC8-Schalter umlegen und die FC-Meldung prüfen. Die letzte Meldung bleibt mit Alter sichtbar, auch bei Linkverlust. Sie kann nach einem Neustart oder einer anderweitigen Änderung überholt sein. EKF-Warnungen werden davon getrennt angezeigt. Siehe [ArduPilot-Quellenauswahl](https://ardupilot.org/copter/docs/common-ekf-sources.html) und [RC-Umschaltmeldung im Quellcode](https://github.com/ArduPilot/ardupilot/blob/master/libraries/RC_Channel/RC_Channel.cpp).

Der Bodenabstand kommt aus `DISTANCE_SENSOR` mit Orientierung „nach unten“; andere Sensororientierungen überschreiben ihn nicht. Er ist die Entfernung entlang der Sensorachse und bei geneigter Drohne nicht automatisch die senkrechte Höhe. Das Programm übernimmt nur vom FC weitergeleitete Werte des MTF-01P; es greift nicht direkt auf den Sensor zu. Ein innerhalb des Messbereichs liegender Wert garantiert allein noch keine gesunde Sensorfusion. Die Felddefinitionen und Einheiten stammen aus der [MAVLink-Dokumentation](https://mavlink.io/en/messages/common.html).

## ELRS und Backpack

1. TX und RX für den tatsächlichen **MAVLink-Modus** konfigurieren. Normale CRSF-Telemetrie allein ist kein beliebiger bidirektionaler MAVLink-Kanal. FC-UART, Baudrate, ELRS-Firmware und Empfänger müssen zusammenpassen.
2. Laut ELRS-Dokumentation Backpack ab Version 1.5.0 verwenden und im ELRS-Lua-Menü `Backpack → Telemetry → WiFi` wählen. Manuell aktiviertes Update-WiFi ist ein anderer Betriebsmodus.
3. Debian-Rechner mit dem Backpack-AP oder demselben Heimnetz verbinden. UDP 14550 gezielt in der Firewall zulassen. Andere Bodenstationen für diesen Test schließen: Portkonflikte und fremde GCS-Heartbeats vermeiden.
4. Verbindung prüfen:

```bash
.venv/bin/python -m drone_control status --connect udpin:0.0.0.0:14550
```

`udpin` lauscht auf Backpack-Telemetrie; Antworten gehen an deren Absender. Ob die konkrete Firmware Befehle zurück zum FC transportiert, wird durch Parameterantworten und Command-ACKs beim Ablauf geprüft. `status` empfängt nur Heartbeats und bestätigt noch keinen Rückkanal. Die Ziel-ID ist standardmäßig 1, GCS-ID 255. Bei Bedarf `--target-system` und `--source-system` setzen; nur einen Copter pro Verbindung betreiben. Ein UDP-Netz ist hier nicht authentifiziert: vertrauenswürdiges lokales Netz verwenden.

### Backpack im Heim-WLAN über elrs_txbp.local erreichen

Wenn Laptop und Backpack im selben lokalen WLAN (z. B. Olymp) sind:

```bash
.venv/bin/python -m drone_control telemetry --backpack
```

`--backpack` verwendet standardmäßig `elrs_txbp.local`. Alternativ einen Host oder die IP aus der Router-Geräteliste angeben:

```bash
.venv/bin/python -m drone_control status --backpack http://elrs_txbp.local/
.venv/bin/python -m drone_control telemetry --backpack 10.0.0.42
```

Die Webadresse dient zur Erkennung, MAVLink läuft weiterhin über UDP. Das Programm liest `/mavlink`, prüft `enabled` und übernimmt die vom Backpack gemeldeten Ports: typischerweise `listen=14555` am Backpack und `send=14550` zum Laptop. Es lauscht lokal auf dem Send-Port des Backpacks und schickt vom selben Socket ein MAVLink-PING an dessen Listen-Port. Dadurch lernt die Firmware die Laptop-IP und kann Telemetrie direkt dorthin senden, statt zunächst auf WLAN-Broadcasts angewiesen zu sein. Das PING ist kein Flugbefehl und kein GCS-Heartbeat; es aktiviert nicht selbst den GCS-Heartbeat-Failsafe. Auch `status --backpack` sendet diesen Anmelde-PING. `telemetry --backpack --passive` liest nur die HTTP-Diagnose und wartet passiv auf UDP, ohne Anmeldung oder Datenanfragen. `--backpack` und `--connect` sind alternative Verbindungsarten.

**„Backpack erreichbar, aber MAVLink-Weiterleitung nicht aktiv“** bedeutet: Im ELRS-Lua-Menü `Backpack → Telemetry → WiFi` wählen, ggf. aus- und wieder einschalten. `WiFi Connectivity → Enable Backpack WiFi` aktiviert den Update-Modus und genügt nicht. Die Drohne muss eingeschaltet und der ELRS-Link aktiv sein. Die Weboberfläche allein bestätigt keine MAVLink-Verbindung. Auch wenn im Sender bereits WiFi steht, kann der Backpack `enabled=false` melden. In diesem Fall Telemetry einmal auf Off und zurück auf WiFi schalten und `/mavlink` erneut prüfen. Steigt `packets_down` bei gleichzeitig `enabled=false`, kommen Pakete am Backpack an, seine MAVLink-UDP-Weiterleitung ist aber laut Eigendiagnose nicht aktiv. Ein reiner Wechsel des Laptop-UDP-Ports behebt das nicht. Das Programm schaltet den Backpack-Modus nicht eigenständig um.

Wenn `.local` unter Debian nicht aufgelöst wird, zunächst die numerische IP verwenden. Für mDNS sind typischerweise `avahi-daemon` und die passende Namensauflösung (`libnss-mdns` bzw. systemd-resolved-Konfiguration) erforderlich. Bei erreichbarer Weboberfläche, aber fehlendem FC-Heartbeat außerdem UDP-Firewall, WLAN-Geräteisolierung und andere aktive Bodenstationen prüfen. Die Erkennung ändert keine Backpack-Einstellungen. Technische Grundlage: [Backpack-Firmware, /mavlink und GCS-IP-Erkennung](https://github.com/ExpressLRS/Backpack/blob/master/lib/WIFI/devWIFI.cpp).

### USB-Menü der Fernsteuerung: HID, SD oder VCP?

**Für die hier beschriebene Steuerung über ein internes ELRS-Modul verwende Backpack-WiFi und UDP.** Keiner der drei USB-Menüpunkte stellt allein eine bidirektionale MAVLink-Verbindung zur Drohne her. Das USB-Kabel an der Fernsteuerung wird für diesen Verbindungsweg nicht benötigt.

| Auswahl an der Fernsteuerung | Funktion | Verwendung mit diesem Programm |
| --- | --- | --- |
| USB Joystick (HID) | Sticks und Schalter als Eingabegerät für den PC, etwa für einen Simulator | Kein MAVLink-Anschluss |
| USB Storage (SD) | Zugriff auf Dateien der SD-Karte | Kein MAVLink-Anschluss |
| USB Serial (VCP) | Virtueller serieller Anschluss; dessen Funktion hängt von der EdgeTX-Konfiguration ab | Allein keine MAVLink-Brücke zum internen ELRS-Modul |

Wenn du ausdrücklich einen seriellen USB-Anschluss der Fernsteuerung benötigst, ist **USB Serial (VCP)** die entsprechende Auswahl. Für unser Programm genügt diese Auswahl aber nicht: Ein unter Debian auftauchendes `/dev/ttyACM0` bestätigt nur den seriellen Anschluss, nicht das MAVLink-Protokoll oder einen Rückkanal zur Drohne. Auch EdgeTX `Telem Mirror` ist keine Zusage einer bidirektionalen MAVLink-Brücke; es spiegelt laut EdgeTX die zum Modulschacht gehenden Telemetriedaten. Deshalb dafür keine zusätzlichen EdgeTX-Einstellungen auf Verdacht ändern.

Die [ExpressLRS-Dokumentation](https://www.expresslrs.org/software/mavlink/#hardware-requirements) verweist für interne TX-Module ausdrücklich auf Backpack-WiFi. Die [EdgeTX-Dokumentation zu seriellen Ports](https://manual.edgetx.org/v2.11/color-radios/radio-settings/hardware) erläutert USB-VCP und Telem Mirror. Für deine Fernsteuerung mit internem ELRS-Modul und Backpack gilt somit weiterhin:

```bash
.venv/bin/python -m drone_control status --connect udpin:0.0.0.0:14550
```

### USB direkt am Flugcontroller oder externen ELRS-Modul

Das folgende USB-Beispiel meint **den Flugcontroller direkt am Rechner**, nicht den USB-Anschluss der Fernsteuerung. Alternativ lässt sich ein geeignetes **externes ELRS-TX-Modul direkt an dessen eigenem USB-Datenanschluss** verwenden, wenn es MAVLink über diesen Anschluss unterstützt. ExpressLRS beschreibt diesen Weg unter [Serial (USB) Connection](https://www.expresslrs.org/software/mavlink/#serial-usb-connection). Der Funklink muss dabei im MAVLink-Modus arbeiten; ein beliebiger Lade- oder Update-Anschluss genügt nicht.

Verfügbare serielle Anschlüsse anzeigen:

```bash
.venv/bin/python -m serial.tools.list_ports -v
```

Den tatsächlich zugehörigen Gerätenamen auswählen (beispielsweise `/dev/ttyACM0` oder `/dev/ttyUSB0`; die Nummer kann wechseln). Zum Test mit direkt angeschlossenem Flugcontroller:

```bash
.venv/bin/python -m drone_control status --connect /dev/ttyACM0 --baud 115200
```

Bei fehlenden USB-Rechten den Benutzer der Gruppe `dialout` hinzufügen und neu anmelden.

## Voraussetzungen am Flugcontroller

Das Programm liest Parameter, verändert sie aber nicht. Vor einem echten Start verlangt es:

- disarmter Quadcopter am Boden und manuell gewähltes `GUIDED`;
- frische Positions-, EKF- und Bodenkontaktmeldungen;
- EKF-Flags für Lage, horizontale/vertikale Geschwindigkeit, relative horizontale Position und vertikale Position; keine konstante oder uninitialisierte Positionslösung;
- aktivierte Arming-Prüfungen (`ARMING_CHECK` ungleich 0; `1` = alle, individuelle Bitmasken ebenfalls unterstützt), aktiven RC-Failsafe (`FS_THR_ENABLE` ungleich null);
- `FS_GCS_ENABLE=5` (Land) und `FS_GCS_TIMEOUT` zwischen 2 und 10 Sekunden;
- `MAV_GCS_SYSID` bzw. bei älteren Versionen `SYSID_MYGCS` passend zur Quell-ID;
- `LAND_SPEED` zwischen 10 und 30 cm/s.

Diese Prüfungen ersetzen keine Prüfung der gesamten FC-Konfiguration. Insbesondere `FS_OPTIONS`, RC-Failsafe-Aktion, Batterie-/EKF-Failsafes und GCS-ID-Bereiche müssen zur verwendeten ArduCopter-Version passen. Welche Failsafes in manuellen Modi gelten sollen, bewusst konfigurieren. Andere Sender mit derselben GCS-ID können die Heartbeat-Ausfallüberwachung unwirksam machen.

MTF-01P/Optical Flow: EKF3 allein bedeutet noch keine gültige Positionshaltung. Sensororientierung, Skalierung, Entfernungsmessung, EKF-Quellen und gegebenenfalls EKF-Origin ohne GPS müssen korrekt eingerichtet sein. Zuerst funktionierende Positionshaltung im RC-Betrieb bestätigen. Keine vorhandenen Sensorparameter blind überschreiben; die unten verlinkte MTF-Dokumentation unterscheidet ArduPilot-Versionen.

## Nur Armen ohne Abheben

Vorschau ohne Verbindung:

```bash
.venv/bin/python -m drone_control arm
```

Tatsächlicher Bodentest **ohne Propeller**:

```bash
.venv/bin/python -m drone_control arm --backpack --execute
```

Der Befehl behält den aktuellen Flugmodus bei, prüft disarmte Motoren, aktivierte Arming-Prüfungen (`ARMING_CHECK` ungleich 0) und vom FC gemeldeten Bodenkontakt. Er sendet einen normalen Arm-Befehl, wartet auf Bestätigung und den Armed-Zustand und beendet sich. Bei einer individuellen `ARMING_CHECK`-Bitmaske protokolliert das Programm den Wert als Hinweis. Es verändert die Auswahl nicht und prüft nicht, ob jede einzelne Auswahl zum Einsatzzweck passt; dafür ist die FC-Konfiguration maßgeblich. ArduPilots konfigurierte Arming-Prüfungen müssen bestanden werden; es gibt kein Force-Arming. Es werden kein Takeoff-, LAND-, RC-Override- oder Moduswechselbefehl und keine GCS-Heartbeats gesendet. Die Missionsdatei wird dafür nicht gelesen; GUIDED und die zusätzlichen Missionsvorprüfungen sind nicht Voraussetzung. Die Telemetrieanzeige vorher beenden.

Bei abgelehntem Arm-Befehl zeigt das Programm die empfangenen `PreArm:`-/`Arm:`-/`Arming:`-Meldungen des FC und den benannten MAVLink-Ergebniscode an. Es wartet nach einer Ablehnung kurz auf nachlaufende Meldungen, ohne erneut zu armen. Wird keine konkrete Begründung empfangen, sagt es dies ausdrücklich. Die letzten drei Arming-Hinweise bleiben auch im Telemetrie-Dashboard mit ihrem Alter sichtbar; historische Meldungen sind kein aktueller Sperrnachweis. Lokale Vorprüfungen (z. B. fehlender Bodenkontakt) geben weiterhin ihren eigenen konkreten Fehler aus.

Armen kann die Motoren bereits drehen lassen. Anschließend per Fernsteuerung disarmen. Der Befehl disarmt nicht selbst beim Beenden; vorhandene Failsafes und ArduPilots automatisches Disarmen können dennoch wirken. Ohne Propeller lässt sich so der Arm-Rückkanal prüfen, nicht die Flugfähigkeit.

## Beispiel fliegen und übernehmen

`examples/hover.toml` enthält 0,5 m Zielhöhe und 5 Sekunden Haltezeit. Die Höhe ist **relativ zu Home**, keine direkte LiDAR-Sollhöhe. Bodenabstand und EKF-Höhe können abweichen; niedrige Startziele müssen mit der konkreten Firmware und dem Bodeneffekt erprobt werden. Eine exakt eingehaltene Höhe von 50 cm wird nicht garantiert. LAND verwendet die FC-Landeregelung einschließlich weiterer Einstellungen wie `LAND_SPEED_HIGH`; dieses Programm schreibt keine Geschwindigkeitsparameter.

Zuerst in SITL, dann ohne Propeller die Verbindung und RC-Modusübernahme prüfen. Für den ersten Flug einen geeigneten freien Testbereich wählen und den RC-Modusschalter griffbereit halten. Der Ablauf beginnt direkt nach erfolgreichen Prüfungen:

```bash
.venv/bin/python -m drone_control run --mission examples/hover.toml --execute
```

An der Fernsteuerung einen echten Modusschalter einrichten, beispielsweise GUIDED / LOITER / ALT_HOLD. Für die Übernahme **in einen anderen Modus umschalten**; Stickbewegungen allein beenden das Skript nicht zuverlässig. Die Übernahme erfolgt im FC unabhängig vom Computer. Sobald ein abweichender Heartbeat eintrifft, verriegelt die Software den Abbruch bis zum nächsten Programmstart. Sie schaltet nie automatisch zurück auf GUIDED. Auch FC-Failsafe-Moduswechsel werden als Steuerungsabgabe behandelt.

Bei Fehler, `Strg+C` oder Linkverlust beendet das Programm Befehle und Heartbeats. Es sendet dann insbesondere keinen LAND-Befehl hinter einer möglichen RC-Übernahme her. Wenn der FC noch autonom fliegt, muss sein konfigurierter GCS-Failsafe landen. Das ist keine sofortige Notlandung: bis zu dessen Timeout kann GUIDED das bisherige Ziel halten. Bei erfolgreichem Ablauf wird LAND aktiv angefordert und bis zum vom FC gemeldeten Disarmen gewartet. Es gibt kein erzwungenes Disarmen in der Luft.

MAVLink hat Übertragungs- und Bearbeitungszeiten: bereits gesendete Befehle lassen sich nicht zurückrufen. Beim Übergang zu LAND besteht ein kurzes Fenster, in dem GUIDED und LAND als erwartete Modi gelten. Eine nahezu gleichzeitige RC-Umschaltung auf genau GUIDED ist daher nicht eindeutig erkennbar. Für Übernahme einen anderen Modus wählen. Sehr kurze Wechsel zwischen zwei Telemetrie-Heartbeats können softwareseitig unbemerkt bleiben.

## Simulation und Grenzen

Siehe [docs/testing.md](testing.md). Unit-Tests prüfen Logik und MAVLink-Verarbeitung; sie sind kein Flugnachweis. Verbindung, Telemetrie und Armen wurden an realer Hardware erprobt; daraus folgt kein Nachweis für einen sicheren autonomen Flug. Die Software unterstützt zunächst ausschließlich den vertikalen Start–Halten–Land-Ablauf; keine Wegpunktnavigation, Hindernisvermeidung oder GUI. Die Haltephase belässt das vom FC gesetzte GUIDED-Startziel aktiv; sie streamt keine RC-Overrides oder Motorbefehle.

## Dokumentation der verwendeten Schnittstellen

- [ArduPilot: Guided-Befehle](https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html)
- [ArduPilot: GCS-Failsafe](https://ardupilot.org/copter/docs/gcs-failsafe.html)
- [ArduPilot: RC-Failsafe](https://ardupilot.org/copter/docs/radio-failsafe.html)
- [ArduPilot: MTF-01 und Sensororientierung](https://ardupilot.org/copter/docs/common-mtf-01.html)
- [ExpressLRS: MAVLink und Backpack-WiFi](https://www.expresslrs.org/software/mavlink/)

## GPS-UART-Rückkanal prüfen

Für eine UBX-MON-VER-Versionsabfrage ohne Änderung der GPS-Konfiguration gibt es `python -m drone_control.gps_probe`. Vorher USB-Passthrough einrichten; die vollständige Anleitung für dein GPS an SERIAL3 steht in [docs/gps-test.md](gps-test.md). Das Werkzeug armt nicht und arbeitet nicht über Backpack-MAVLink.

## Akkudaten dauerhaft an EdgeTX senden

ExpressLRS wandelt `BATTERY_STATUS` (MAVLink-Nachricht 147, Batterie-ID 0) in die EdgeTX-Sensoren RxBt, Curr, Capa und Bat% um. `drone_control telemetry` fordert diese Nachricht mit 1 Hz auf seiner Verbindung an. Für eine Anzeige ohne laufendes Programm unter ArduCopter 4.6.2 die passende gespeicherte Streamrate `SRx_EXTRA3 = 1` setzen und den FC neu starten.

Die SR-Nummer folgt der Reihenfolge der als MAVLink konfigurierten seriellen Anschlüsse; sie entspricht nicht automatisch der UART-Nummer. Beispiel der erprobten Konfiguration: USB/SERIAL0 → SR0, SERIAL4/MAVLink1 → SR1, SERIAL6/MAVLink2/ELRS → SR2, SERIAL8/MAVLink2 → SR3. Hier ist `SR2_EXTRA3 = 1` richtig. Bei einer anderen Portkonfiguration die Zuordnung erneut prüfen. EXTRA3 enthält weitere Nachrichten; 1 bedeutet die gewünschte Gruppenrate in Hz, keine Sensormessrate oder Akkuwarnschwelle. Die Einstellungen im Nachrichtenfenster einer USB-Bodenstation gelten nicht automatisch für die ELRS-Verbindung.

Nach dem Speichern den FC neu starten und die GX15 ohne laufende Bodenstation prüfen. Bei Bedarf in EdgeTX neue Sensoren suchen. Diese Einstellung wurde für die genannte Konfiguration erfolgreich erprobt. Ab ArduPilot 4.7 heißen die Streamparameter anders; siehe [ArduPilot: Datenraten](https://ardupilot.org/dev/docs/mavlink-requesting-data.html).
