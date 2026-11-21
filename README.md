# Rollladen

Custom Integration für [Home Assistant](https://www.home-assistant.io/) zur Steuerung von Rollläden.

Die Integration fährt die Rollläden selbst: morgens hoch und abends runter nach Uhrzeit, Helligkeit oder Sonnenstand. Sie beschattet bei Sonne, folgt dem Fenstergriff, schützt Türen vor dem Aussperren, erkennt Handbetrieb, bedient die Wandtaster und passt bei Frost auf. Alles wird in der Oberfläche von Home Assistant eingerichtet. Es sind keine Helfer, Automationen oder YAML nötig.

> **Stand:** Version 0.1.6, erste Fassung. Die Logik ist ein Port der AppDaemon-App „ASC“ (v0.27) und mit Tests abgesichert, im Alltag aber noch nicht erprobt. Die Oberfläche ist nur auf Deutsch.

---

## Inhalt

- [Was die Integration kann](#was-die-integration-kann)
- [Begriffe](#begriffe)
- [Voraussetzungen](#voraussetzungen)
- [Installation](#installation)
- [Einrichtung](#einrichtung)
- [Entities](#entities)
- [So entscheidet die Steuerung](#so-entscheidet-die-steuerung)
- [Taster](#taster)
- [Frostschutz](#frostschutz)
- [Umstellung vom Altsystem](#umstellung-vom-altsystem)
- [Neustart und Speicherung](#neustart-und-speicherung)
- [Umbenennen und fehlende Entities](#umbenennen-und-fehlende-entities)
- [Bekannte Grenzen](#bekannte-grenzen)
- [Entwicklung](#entwicklung)
- [Versionen](#versionen)

---

## Was die Integration kann

- **Tagesfahrten** je Rollladen und Richtung mit eigenem Zeitfenster (frühestens / spätestens) und drei Fahrmodi: Zeit, Helligkeit, Astro.
- **Anwesenheit** je Richtung: immer, nur wenn niemand da ist, oder gar nicht.
- **Fenstergriff:** Nachts folgt der Rollladen dem Griff (zu / gekippt / offen).
- **Tür-Sicherung (Aussperrschutz):** Bei offener Tür fährt der Rollladen nie zu, beim Öffnen sofort ganz auf.
- **Handbetrieb-Erkennung:** Von Hand gefahren (Taster, Dashboard, andere Automation) wird respektiert, nachts mit einer Sperre und späterer Rückfahrt.
- **Beschattung** nach Sonnenstand, Helligkeit und Außentemperatur, mit Hysterese.
- **Wandtaster:** kurz = auf/zu, lang = Stopp, mehrere Taster je Rollladen.
- **Frostschutz:** bei Kälte und Nässe nur einen Spalt öffnen und auf Handbefehl warten, mit Push-Nachricht.
- **Klartext-Status** je Rollladen: was er zuletzt getan hat und warum.

---

## Begriffe

| Begriff | Bedeutung |
|---|---|
| **Anlage** | Die Integration selbst. Gerät „Rollladen“ mit den globalen Schaltern und Einstellungen. |
| **Rollladen** | Ein Cover mit Position. Jeder bekommt ein eigenes Gerät, z. B. „WZ Süden“. |
| **Phase** | Was die Automatik gerade will: **auf** (Tag) oder **zu** (Nacht). |
| **Tagesfahrt** | Die automatische Hoch- bzw. Runterfahrt, je einmal am Tag. Sie setzt die Phase. |
| **Handsperre** | Nach einer Handfahrt in der Zu-Phase ruht die Automatik eine Zeit lang. |
| **Blocking-Zeit** | Kurz vor einer Tagesfahrt keine Fahrt in die Gegenrichtung (z. B. nicht zufahren, wenn er gleich hochfährt). |

---

## Voraussetzungen

- Home Assistant mit Marketplace (ab 2026.11) oder HACS.
- Je Rollladen eine `cover`-Entity mit Position (0 = zu, 100 = auf).
- Ein Außen-Helligkeitssensor (Lux).
- Optional: Personen (`person`) für die Anwesenheit, Außentemperatur, Fenstergriffsensoren (`closed` / `tilted` / `open`, z. B. HmIP-SRH), Taster als `event`-Entities, für den Frostschutz Niederschlag, Luftfeuchte und eine Wetter-Entity.

---

## Installation

1. In Home Assistant den **Marketplace** öffnen (Einstellungen → Marketplace; bei älteren Versionen HACS).
2. Dieses Repository als benutzerdefiniertes Repository hinzufügen: `https://github.com/Efka00/ha-rollladen`, Kategorie **Integration**.
3. „Rollladen“ installieren und Home Assistant neu starten.
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Rollladen*.

---

## Einrichtung

Die Integration kann nur einmal eingerichtet werden. Beim Hinzufügen werden die **Einstellungen der Anlage** abgefragt, Rollläden kommen danach dazu. Jede Einstellung hat im Dialog einen Hilfetext. Später: *Einstellungen → Geräte & Dienste → Rollladen → Konfigurieren* mit dem Menü **Anlage einstellen**, **Frostschutz**, **Rollladen hinzufügen / bearbeiten**, **Rollläden löschen**.

### Anlage

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Helligkeitssensor | – | Pflicht. Für den Fahrmodus Helligkeit und die Beschattung. |
| Personen | leer | Dropdown, mehrere möglich. Jemand da = mindestens eine Person zuhause. Leer, oder eine Person unbekannt und keine zuhause = jemand da. |
| Außentemperatur | leer | Für Beschattung und Frostschutz. |
| Beschattungsposition | 40 % | |
| Sonnenhöhe mindestens | 20° | Darunter keine Beschattung. |
| Beschatten ab Außentemperatur | 18 °C | |
| Beschatten ab / Entschatten unter Helligkeit | 30 000 / 15 000 lx | Hysterese gegen Flattern. |
| Helligkeit mitteln über | 5 min | Zeitgewichteter Mittelwert gegen Ausreißer. 0 = letzter Wert. |
| Mindestabstand Beschattung | 10 min | Zwischen zwei Entscheidungen wegen der Helligkeit. |
| Push-Nachrichten an | leer | Handys aus der Companion-App, mehrere möglich. |

### Frostschutz

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Frostposition | 10 % | Höchstens so weit öffnet die Automatik bei Frost. 10 % = Lüftungsschlitze offen, Endleiste liegt auf. |
| Hysterese | 1 K | Kalt endet erst so viel über der Schwelle. |
| Nässe der letzten | 24 h | So weit zurück zählt Nässe. |
| Niederschlagssensor | leer | Wert > 0 = Niederschlag. Fällt er aus, gilt es als nass. |
| Luftfeuchtesensor / Feucht ab | leer / 90 % | Zählt nur mit Plusgraden. |
| Wetter | leer | Regen, Schnee oder Hagel zählen als Niederschlag. |

Ein- und ausgeschaltet wird der Frostschutz über den Schalter **Frostschutz**, die Temperaturschwelle steht an der Entity **Frostschutz unter** (Standard 1,5 °C).

### Rollladen hinzufügen

| Einstellung | Standard | Bedeutung |
|---|---|---|
| Name | – | Raum und Lage, z. B. „Wohnzimmer Essecke“, bei nur einem Rollladen im Raum nur der Raum. Der Name wird Teil der Entity-IDs (`switch.wohnzimmer_essecke_automatik`). Den Bereich übernimmt das Gerät nach dem Anlegen vom Cover. |
| Cover | – | Der Rollladen. |
| Taster | leer | Eine oder mehrere `event`-Entities. |
| Ereignis kurz / lang | `press_short` / `press_long` | `event_type` der Taster (Homematic IP). |
| Fenstergriff | leer | Griffsensor. |
| Tür | aus | Aussperrschutz, braucht einen Griffsensor. |
| Position gekippt / offen | 25 / 80 % | Ziel in der Zu-Phase je Griffstellung. Tür: offen = 100. |
| Beschattung ab / bis Azimut | leer | Sonnenrichtung in Grad (Süd = 180). Beide leer = keine Beschattung. |
| Handsperre | 120 min | |
| Vor der Morgenfahrt nicht zufahren | 60 min | |
| Vor der Abendfahrt nicht auffahren | 60 min | |
| Frostschutz | an | Aus z. B. für Türen unter einem Dach. |

Neue Rollläden starten mit **Automatik aus**.

---

## Entities

**Anlage** (Gerät „Rollladen“)

| Entity | Art | Bedeutung |
|---|---|---|
| Automatik | Schalter | Hauptschalter für alle Rollläden. Startet aus. |
| Beschattung | Schalter | Beschattung global an/aus. |
| Frostschutz | Schalter | Frostschutz global an/aus. |
| Helligkeit hoch ab / runter unter | Zahl | Lux-Schwellen für den Fahrmodus Helligkeit (Standard 700 / 600 lx). |
| Frostschutz unter | Zahl | Temperaturschwelle (Standard 1,5 °C). |
| Frostschutz aktiv | Binärsensor | Schalter an, kalt und nass. Attribut `status` sagt im Klartext, warum er greift oder nicht, z. B. „Nicht aktiv: 4,9 °C, kalt erst unter 1,5 °C“ oder „Aktiv: -1,0 °C unter 1,5 °C, Niederschlag zuletzt 05:00“. Weitere Attribute: kalt, nass, Grund, letzter Niederschlag. |

**Je Rollladen**

| Entity | Art | Bedeutung |
|---|---|---|
| Automatik | Schalter | Aus = nur noch Taster und Hand. |
| Hoch frühestens / spätestens | Uhrzeit | Zeitfenster der Morgenfahrt (Standard 07:30 / 09:00). |
| Runter frühestens / spätestens | Uhrzeit | Zeitfenster der Abendfahrt (Standard 19:00 / 22:30). |
| Fahrmodus hoch / runter | Auswahl | Zeit, Helligkeit, Astro. |
| Anwesenheit hoch / runter | Auswahl | Immer, Nur wenn niemand da ist, Aus. |
| Beschattung | Auswahl | Aus, Immer, Nur wenn jemand da ist, Nur wenn niemand da ist (nur mit Azimut). |
| Status | Sensor | Letzte Aktion mit Grund. Attribute: Phase, Soll, Position, Griff, Tür-Sperre, Handsperre bis, Blocking, Beschattung, Frostschutz, Helligkeit (Mittelwert). |
| Position | Sensor (Diagnose) | Aktuelle Position des Covers in %. Attribute: gesteuertes Cover, Name, Griff, Taster, `letzter_befehl` und `protokoll` (die letzten 12 Befehle der Integration mit Uhrzeit und Grund, neueste zuerst). Steht eine Fahrt am Cover nicht im Protokoll, kam sie nicht von der Integration. |
| Phase | Sensor | auf / zu. |
| Nächste Hochfahrt / Runterfahrt | Sensor | Uhrzeit zum Lesen: „19:00“ (heute), „morgen 07:49“, sonst Wochentag. Genauer Zeitpunkt im Attribut `zeitpunkt`. |
| Letzte Hochfahrt / Runterfahrt | Sensor | Tages-Merker, Anzeige wie oben („gestern 19:00“), standardmäßig deaktiviert. |
| Handsperre | Binärsensor | Attribut `bis`. |
| Beschattet | Binärsensor | Nur mit Azimut. Attribut `grund`. |

---

## So entscheidet die Steuerung

Ausgewertet wird jede Minute und sofort bei Änderungen (Helligkeit, Anwesenheit, Griff, Position, Einstellungen).

**Helligkeit.** Fahrmodus „Helligkeit“ und Beschattung rechnen mit dem zeitgewichteten Mittelwert der letzten 5 min (einstellbar). Ein Wert gilt, bis der Sensor den nächsten meldet. Eine einzelne Fehlmeldung, etwa 0 lx nach einem Neustart des Sensors, die eine Minute steht, zählt damit nur zu einem Fünftel. Meldet der Sensor `unavailable` oder `unknown`, gilt der letzte Wert weiter. Erst nach 15 min Ausfall gilt „kein Wert“, und „Helligkeit“ fährt wie „Astro“. Den Mittelwert zeigt der Status im Attribut `helligkeit_mittel`.

**Phase.** Runterfahrt heute gefahren → zu. Hochfahrt heute gefahren → auf. Sonst nach Uhrzeit: auf zwischen Morgen- und Abendziel.

**Morgenfahrt** (einmal am Tag, läuft auch bei Handsperre). Erlaubt ab „Hoch frühestens“ bis „Runter frühestens“, holt also nach, wenn HA später startet.
- *Zeit:* ab „Hoch frühestens“.
- *Helligkeit:* sobald die Helligkeit die Schwelle erreicht, spätestens bei „Hoch spätestens“ (Zwangsfahrt).
- *Astro:* zum Sonnenaufgang, geklemmt ins Zeitfenster.
- Ziel 100 %, oder direkt die Beschattungsposition, wenn beschattet würde.

**Abendfahrt** (einmal am Tag, nicht bei Handsperre). Ab „Runter frühestens“, Modi analog. Ziel ist die Griffposition: zu 0 %, gekippt 25 %, offen 80 %. Ohne Helligkeitswert fährt „Helligkeit“ wie „Astro“.

**Griff** (nur in der Zu-Phase). Der Rollladen folgt dem Griff, auch während einer Handsperre. In der Auf-Phase wird der Griff ignoriert. Meldet der Griffsensor kurz `unavailable` oder `unknown` (Neustart, Funkabbruch), zählt das nicht als Griffwechsel. Ein Fenster behält solange den letzten gültigen Zustand, eine Tür nicht (siehe Tür-Sicherung).

**Tür-Sicherung.** Ist der Griff einer Tür nicht `closed`/`tilted` (also auch bei totem Sensor), verweigert die Automatik jede Fahrt unter 100 %. Tür öffnen fährt sofort auf 100 %, egal welche Phase oder Sperre. Handfahrten werden nicht zurückgedreht.

**Handbetrieb.** Eine Positionsänderung, die nicht zum eigenen Befehl passt (außer in den 90 s Fahrzeit danach), gilt als Handfahrt. Ausgewertet wird erst, wenn die Position 3 s still steht, verglichen mit der Position vor der Fahrt. So gibt eine Fahrt einen einzigen Status-Eintrag statt eines je Zwischenstand:
1. Ganz auf ab 2 h vor „Hoch frühestens“ und vor „Runter frühestens“ → Auf-Phase, keine Sperre.
2. In der Auf-Phase ohne Beschattung → bleibt stehen.
3. Nach unten ab „Runter frühestens“ → Zu-Phase und Sperre.
4. Sonst (Zu-Phase oder während der Beschattung) → Sperre. Nach Ablauf fährt er zurück auf die Griffposition.

**Blocking-Zeiten.** Vor der Morgenfahrt kein Zufahren, vor der Abendfahrt kein Auffahren. Gilt für Griff und Rückfahrt, nicht für die Tagesfahrten.

**Fahrabstand.** Automatik-Fahrten starten mit 1,5 s Abstand, damit bei gleicher Fahrzeit nicht alle Motoren gleichzeitig anlaufen. Taster fahren sofort. Während HA herunterfährt, schickt die Integration keine Fahrbefehle mehr.

**Beschattung** (nur Auf-Phase). Beschattet wird, wenn alles zutrifft: Schalter an, Automatik an, Modus passt zur Anwesenheit, keine Handsperre, Fenster zu, Sonne mindestens 20° hoch und im Azimutbereich, mindestens 18 °C, Helligkeit über 30 000 lx. Entschattet wird sofort, wenn eine Bedingung wegfällt, wegen der Helligkeit erst unter 15 000 lx. Zwischen zwei Helligkeits-Entscheidungen liegen mindestens 10 min.

---

## Taster

| Druck | Rollladen steht | Rollladen fährt |
|---|---|---|
| kurz | ganz zu → **auf**, sonst → **zu** | **Gegenrichtung** |
| lang | **Stopp** | **Stopp** |

Im Zweifel zweimal drücken: Der erste Druck fährt zu, der zweite kehrt um. Homematic IP sendet `press_long` beim Halten etwa alle 0,3 s erneut. Die Integration stoppt beim ersten und zählt die Wiederholungen nicht mit, langes Halten ist ein einziger Stopp. Tasterfahrten sind Handfahrten (Handsperre, Frostfreigabe) und funktionieren auch bei ausgeschalteter Automatik.

---

## Frostschutz

Der Frostschutz greift, wenn der Schalter an ist und es **kalt und nass** ist:
- **Kalt:** Außentemperatur unter „Frostschutz unter“, aus erst 1 K darüber.
- **Nass:** in den letzten 24 h Niederschlag (Sensor oder Wetter), oder über 0 °C feucht (Luftfeuchte ab 90 %). Ohne Nässequelle zählt nur die Temperatur. Fällt der Niederschlagssensor aus, gilt es als nass.

Dann öffnet die Automatik höchstens bis zur Frostposition (10 %), bei der Morgenfahrt, beim Griff und bei der Rückfahrt nach der Sperre. Schließen bleibt unbegrenzt. Je Rollladen und Tag kommt eine Push-Nachricht. Jede Handfahrt gibt den Rollladen bis Tagesende frei. Die Tür-Sicherung hat Vorrang. Den Notbetrieb der Rollladenmodule fasst die Integration nicht an.

---

## Umstellung vom Altsystem

Die Integration startet mit Automatik aus. Rollladen für Rollladen umstellen:

1. Rollladen in der Integration anlegen (Werte unten).
2. Zeiten, Fahrmodus, Anwesenheit und Beschattung an seinen Entities einstellen wie bisher.
3. Im Altsystem: ASC-Automatik des Rollladens aus (`input_boolean.rollladen_*_auto`) und die **Taster-Automation deaktivieren**. Sonst reagieren beide auf denselben Taster und heben sich auf.
4. Automatik des Rollladens in der Integration an, Anlagen-Automatik an.

| Rollladen | Cover | Taster | Griff | Tür | offen | Azimut |
|---|---|---|---|---|---|---|
| Abstellkammer | `cover.eg_ak_ro` | `event.hmipw_e01_eg_ak_tt_s2` | `sensor.hmip_eg_ak_fk` | | 80 | 45–135 |
| Gäste-WC | `cover.eg_wc_ro` | `event.hmipw_e01_eg_wc_tt_s2` | `sensor.hmip_eg_wc_fk` | | 80 | 315–359 |
| Küche | `cover.eg_kz_ro` | `event.hmipw_e01_eg_kz_tt1_s1`, `event.hmipw_e02_eg_kz_tt2_s1` | `sensor.hmip_eg_kz_fk` | | 80 | 45–135 |
| Wohnzimmer Süd | `cover.eg_wz_ro1` | `event.hmipw_e02_eg_wz_tt1_s1` | `sensor.hmip_eg_wz_fk1` | | 80 | 105–230 |
| Wohnzimmer Essecke | `cover.eg_wz_ro2` | `event.hmipw_e02_eg_wz_tt1_s3` | `sensor.hmip_eg_wz_fk2` | ja | 100 | 205–270 |
| Wohnzimmer Terrasse | `cover.eg_wz_ro3` | `event.hmipw_e02_eg_wz_tt1_s5` | `sensor.hmip_eg_wz_fk3` | ja | 100 | 205–270 |
| Wohnzimmer Couch | `cover.eg_wz_ro4` | `event.hmipw_e02_eg_wz_tt1_s7` | `sensor.hmip_srh_0007d8a99fc532` | | 80 | 205–270 |
| Kinderzimmer 2 West | `cover.og_kiz2_ro1` | `event.hmipw_e03_og_kiz2_tt_s1` | `sensor.hmip_og_kiz2_fk1` | | 80 | 205–270 |
| Kinderzimmer 2 Nord | `cover.og_kiz2_ro2` | `event.hmipw_e03_og_kiz2_tt_s3` | `sensor.hmip_og_kiz2_fk2` | | 80 | 315–359 |
| Bad | `cover.og_bad_ro` | `event.hmipw_e02_og_bad_tt_s1` | `sensor.hmip_og_bad_fk` | | 80 | 315–359 |
| Schlafzimmer Süd | `cover.og_sz_ro1` | `event.hmipw_e02_og_sz_tt_s2` | `sensor.hmip_og_sz_fk1` | | 80 | 105–230 |
| Schlafzimmer West | `cover.og_sz_ro2` | `event.hmipw_e02_og_sz_tt_s4` | `sensor.hmip_og_sz_fk2` | | 80 | 205–270 |
| Kinderzimmer 1 | `cover.og_kiz1_ro` | `event.hmipw_e03_og_kiz1_tt_s2` | `sensor.hmip_og_kiz1_fk` | | 80 | 105–230 |

Frostschutz für Wohnzimmer Essecke und Wohnzimmer Terrasse ausschalten (unter dem Terrassendach). Anlage: Helligkeit `sensor.au_gt_sen_light_illuminance`, Personen aus dem Dropdown, Temperatur `sensor.rosenthal_temperatur`, Niederschlag `sensor.rosenthal_niederschlag_1h`, Luftfeuchte `sensor.rosenthal_luftfeuchte`.

Wenn alle umgestellt sind: AppDaemon-App, Taster-Automationen und Helfer entfernen, Dashboards (Hardware-Ansicht ASC, Merker-Kacheln in der Hausübersicht) auf die neuen Entities umstellen.

---

## Neustart und Speicherung

Gespeichert und über Neustarts erhalten: Anlagenschalter und -werte, Einstellungen je Rollladen, Tages-Merker, Handsperre, Beschattungszustand, die zuletzt selbst kommandierte Position, der letzte gültige Griffzustand, das Befehlsprotokoll, Frostfreigabe und der Frostzustand mit letztem Niederschlag. Die erste Auswertung läuft 10 s nach dem Start von HA.

---

## Umbenennen und fehlende Entities

Benennst du ein Cover, einen Griff, einen Taster oder einen Anlagen-Sensor um („Entitäts-ID ändern“), übernimmt die Integration die neue ID selbst in ihre Einstellungen und lädt neu. Das klappt nur, solange sie geladen ist.

Gibt es eine Entity aus den Einstellungen nicht mehr oder ist sie deaktiviert, steht unter **Einstellungen → Reparaturen** ein Eintrag mit der Liste. Neu zuordnen unter **Konfigurieren**. Der Eintrag verschwindet, sobald alles wieder da ist.

---

## Bekannte Grenzen

- Der Azimutbereich darf nicht über 0° gehen. Bei mindestens 20° Sonnenhöhe steht die Sonne in Mitteleuropa ohnehin nie im Norden.
- Handbetrieb wird über die Position erkannt. Eine Handfahrt, die genau auf der zuletzt kommandierten Position endet, ist unsichtbar. Taster sind davon ausgenommen.
- Ein angefrorener Rollladen ist nicht erkennbar, wenn das Cover seine Position nur aus der Fahrzeit rechnet. Der Frostschutz arbeitet deshalb über Temperatur und Nässe.

---

## Entwicklung

Die Entscheidungslogik steht in `custom_components/rollladen/logik.py` und kommt ohne Home Assistant aus. Tests:

```bash
python3 -m unittest discover -s tests -v
```

---

## Versionen

- **0.1.6** (21.11.2026): Handbetrieb wird erst nach Fahrtende ausgewertet (3 s Stillstand). Eine Handfahrt ergibt einen Status-Eintrag statt etwa 18. Frostschutz aktiv hat ein Attribut `status` mit Klartext-Begründung.
- **0.1.5** (20.11.2026): Diagnose-Sensor heißt „Position“ und zeigt die Position des Covers in %. Das Cover steht im Attribut `cover`.
- **0.1.4** (20.11.2026): Nächste und letzte Fahrten als Uhrzeit („19:00“, „morgen 07:49“) statt „in 8 Stunden“. Genauer Zeitpunkt im Attribut `zeitpunkt`.
- **0.1.3** (20.11.2026): Langer Tastendruck stoppt genau einmal, auch wenn `press_long` beim Halten wiederholt kommt. Gäste-WC ohne Sonderregel.
- **0.1.2** (20.11.2026): Helligkeit als zeitgewichteter Mittelwert (Vorgabe 5 min), damit Ausreißer des Sensors nichts auslösen. Kurze Sensorausfälle überbrückt der letzte Wert.
- **0.1.1** (20.11.2026): Diagnose-Sensor „Cover“ mit Befehlsprotokoll. Anwesenheit als Mehrfachauswahl der Personen. Griffsensor `unavailable`/`unknown` löst keine Fahrt mehr aus (bisher fuhr ein gekipptes Fenster nachts beim Neustart kurz zu). 1,5 s Abstand zwischen Automatik-Fahrten, keine Fahrbefehle beim Herunterfahren. Umbenannte Entities werden übernommen, fehlende unter „Reparaturen“ gemeldet. Entity-IDs ohne doppelten Raumnamen: Der Bereich kommt erst nach dem Anlegen ans Gerät.
- **0.1.0** (20.11.2026): Erste Fassung. Port von ASC v0.27 mit Taster, Frostschutz (Nässeprüfung) und Speicherung von Handsperre und Beschattung. Korrektur gegenüber ASC: Ohne Helligkeitswert fährt „Helligkeit“ jetzt wirklich zum Sonnenaufgang statt erst zur Spätzeit.

## Lizenz

MIT
