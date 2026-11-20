# Bestandsaufnahme Altsystem (Stand 19.11.2026)

Aus HA ausgelesen (ha-mcp). AppDaemon-Quelle: `Altsystem/asc_rollladen.py` v0.27 (seit 20.11.2026, nur lokal, nicht im Repo).

## Ziel (19.11.2026, mit Martin)

- **Alles in eine Integration.** Keine Helfer, keine Blueprints, keine Rollladen-Automationen mehr. Updates über den Marketplace.
- Vorbild ist die Integration Bewässerung (`Efka00/ha-bewaesserung`): Hub mit `single_config_entry`, ein Gerät je Rollladen, Einstellungen als Entities, Optionsmenü zum Hinzufügen und Bearbeiten.
- **Nur die 13 Innenrollläden.** Schuppen und Terrasse bleiben bei ihren Automationen.
- **Komfortfunktion Schlafzimmer bleibt draußen** (in `og_schlafzimmer_beleuchtung`). Ihr `close_cover` ist für ASC heute eine Handfahrt: nach `down_early` (19:00) setzt sie den Runter-Merker (Phase zu) und sperrt 120 min. Die Integration übernimmt das Verhalten unverändert.
- **Umstellung über den Automatik-Schalter je Rollladen**, keine Übernahme alter Werte nötig. Die Integration startet mit Automatik aus. Je Rollladen: ASC-Auto aus → Integration-Automatik an.
  Achtung Taster: Taster-Automation und Integration dürfen nicht gleichzeitig auf denselben Taster reagieren, sonst hebt der zweite Toggle den ersten auf. Taster-Automation des Rollladens beim Umschalten deaktivieren (oder Taster in der Integration erst dann zuordnen).
- AppDaemon-Quelle kommt am 20.11.2026.

## Architektur heute: vier Stellen fahren Rollläden

| Wer | Was | Rollläden |
|---|---|---|
| **AppDaemon „ASC“** | Automatik: Hoch/Runter nach Helligkeit bzw. Zeitfenster (früh/spät), Beschattung, Sperren (Fenstergriff, Tür), Anwesenheit, Handbetrieb-Erkennung, Zwangsfahrt zur Spätzeit. Veröffentlicht `sensor.asc_info_*` (per `set_state`, nicht in der Registry). | 13 HBW-Rollläden |
| **13 Taster-Automationen** | Kurz = Auf/Zu über Merker (`input_select.*_merker`), lang = Stopp. Je zwei Zweige halten den Merker nach, wenn anderweitig gefahren wurde. `mode: single`. | je einer |
| **`automation.og_schlafzimmer_beleuchtung`** | Komfort: Bettlicht oder Nachtlicht zwischen 19 und 21 Uhr → `cover.close_cover` auf SZ Süd + West. | `og_sz_ro1`, `og_sz_ro2` |
| **`automation.schuppen_rolladen`** | Z2M-Taster (Terrasse + Schuppen) auf/zu, Status-LED `light.eg_wz2_led1`, abends nach Sonnenuntergang zu, sobald `cover.eg_wz_ro3` 1 min zu ist. | `au_gt_ro_schuppen` |
| **`automation.terrassenabdeckung_automation`** | Dualtaster: 1× = toggle Sonnenschutz, 2× = Stopp, lang = Markise aus/ein. Taster sendet jedes Event doppelt → `single` + 1 s Entprellung. | Terrasse (3) |

Nur lesend (bleiben unverändert, weil die `cover.*`-Entities bleiben):
- `automation.anwesenheit_fensterkontrolle_bei_verlassen`: meldet offenen Schuppen beim Verlassen (kein Zufahren, Klemmgefahr).
- Diverse Licht-Automationen (Abstellkammer, Diele EG, Küche, Gäste-WC, Ankleide, Bad, KiZ1, Schuppen, Terrasse, `testak`): Treffer auf `cover.` in der Konfiguration, **steuern aber keine Rollläden** (Suche nach `open_cover`/`close_cover`/`set_cover_position`). Im Detail noch nicht geprüft.

Keine Skripte, keine Szenen. `set_cover_position` nutzt heute keine Automation (nur ASC, vermutlich).

## Rollläden und Hardware

Alle 13 Innenrollläden: Plattform `hbw_modbus` (eigene Integration), `device_class: shutter`, `supported_features: 15` (auf, zu, Position, Stopp), Attribute `position_known`, `teach_step`, `moves`. Einlernfahrten am 13./14.11.2026.

| Cover | ASC-Name | HBW-Kanal | Taster (Event-Entity) | Area |
|---|---|---|---|---|
| `cover.eg_ak_ro` | Abstellkammer | A05/2 | `event.hmipw_e01_eg_ak_tt_s2` | Abstellkammer |
| `cover.eg_kz_ro` | Küche | A05/3 | `event.hmipw_e01_eg_kz_tt1_s1` + `event.hmipw_e02_eg_kz_tt2_s1` | Küche |
| `cover.eg_wc_ro` | Gäste-WC | A05/4 | `event.hmipw_e01_eg_wc_tt_s2` (lang = **`press_long_release`**) | Gäste-WC |
| `cover.eg_wz_ro1` | WZ Süden | A05/1 | `event.hmipw_e02_eg_wz_tt1_s1` | Wohnzimmer |
| `cover.eg_wz_ro2` | WZ Essecke | A06/2 | `event.hmipw_e02_eg_wz_tt1_s3` | Wohnzimmer |
| `cover.eg_wz_ro3` | WZ Terrasse | A06/3 | `event.hmipw_e02_eg_wz_tt1_s5` | Wohnzimmer |
| `cover.eg_wz_ro4` | WZ Couch | A06/4 | `event.hmipw_e02_eg_wz_tt1_s7` | Wohnzimmer |
| `cover.og_bad_ro` | Bad | A10 | `event.hmipw_e02_og_bad_tt_s1` | Badezimmer |
| `cover.og_kiz1_ro` | KiZ1 | A06/1 | `event.hmipw_e03_og_kiz1_tt_s2` | KiZ1 |
| `cover.og_kiz2_ro1` | KiZ2 West | A07/2 | `event.hmipw_e03_og_kiz2_tt_s1` | Ankleide |
| `cover.og_kiz2_ro2` | KiZ2 Nord | A07/3 | `event.hmipw_e03_og_kiz2_tt_s3` | Ankleide |
| `cover.og_sz_ro1` | SZ Süd | A07/4 | `event.hmipw_e02_og_sz_tt_s2` | Schlafzimmer |
| `cover.og_sz_ro2` | SZ West | A07/1 | `event.hmipw_e02_og_sz_tt_s4` | Schlafzimmer |

Alle Taster sind HmIP-Wired über `homematicip_local`, Events `press_short` / `press_long` (Ausnahme Gäste-WC). Die Küche hat zwei Bedienstellen → die Integration nimmt mehrere Taster je Rollladen.

Außen (nicht ASC):
- `cover.au_gt_ro_schuppen`: Shelly, Position, dient als Tür.
- `cover.terrasse_markise` (awning), `cover.terrasse_sonnenschutz_links/_rechts` (blind): Overkiz, alle mit Stopp.

## Helfer

Global (4):
| Entity | Zustand 19.11. |
|---|---|
| `input_boolean.asc_master` | on |
| `input_boolean.asc_beschattung_aktiv` | off |
| `input_number.asc_lux_schwelle_hoch` | 700 lx |
| `input_number.asc_lux_schwelle_runter` | 600 lx |

Pro Rollladen (×13, Präfix `rollladen_<name>_`):
| Entity | Bemerkung |
|---|---|
| `input_select.<cover>_merker` | Auf/Zu, Schattenzustand der Taster-Automation |
| `input_boolean.…_auto` | Automatik an/aus |
| `input_datetime.…_zeit_hoch_fruh` / `_spat` | Zeitfenster Hoch |
| `input_datetime.…_zeit_runter_fruh` / `_spat` | Zeitfenster Runter |
| `input_datetime.…_letzte_hochfahrt` / `_runterfahrt` | Tages-Merker (bestimmen die Phase!), nicht nur Statistik |
| `input_select.…_fahrmodus_hoch` / `_runter` | time / brightness / astro |
| `input_select.…_modus_hoch` / `_runter` | Anwesenheit: always / absent / off |
| `input_select.…_beschattung` | off / always / home / absent |
| `sensor.asc_info_<name>` | von AppDaemon, Attribute siehe unten |

Summe: 4 global + 13 × 13 Helfer = **173 Helfer**, dazu 13 AppDaemon-Sensoren und 16 Automationen.

Stand der Selects am 20.11.: Fahrmodus fast überall `brightness` (Abstellkammer `astro`). Anwesenheit Hoch `absent` bei KiZ1, SZ Süd, SZ West. **Bad komplett `off`** (fährt nie automatisch). Beschattung `always` bei KiZ1, KiZ2 West, SZ Süd, SZ West, sonst `off` (global ist sie ohnehin aus).

Auffällig: Die Helfer der Abstellkammer haben die ID `rollladen_ankleide_*`, heißen aber „Abstellkammer“ (umbenannt).

## `sensor.asc_info_*` (zeigt, was ASC kann)

Beispiel WZ Couch, 19.11. 17:33:
```
state: 0          next_up: 20.11.2026 - 08:00   next_down: 19.11.2026 - 22:30
mode_up/down: brightness       anwesenheit_up/down: always     zuhause: ja
griff: closed     beschattung: off   beschattet: nein   beschattung_grund: Master aus
phase: auf        soll: 100          sperre / tuer_sperre / blocking: –
last_drive: 19.11.2026 - 08:00       position: 0       last_position: 0
grund: Handbetrieb 0% (Auf-Phase, bleibt)
```
Küche: `grund: Zwangsfahrt (Spätzeit)`.

## ASC-Logik (`asc_rollladen.py` v0.27)

Ein AppDaemon-Controller für alle 13 Rollläden. Wertet jede Minute aus (Tick) und zusätzlich bei Änderungen an Lux, Schwellen, Master, Anwesenheit, Beschattungs-Master, Temperatur, den Helfern eines Rollladens, dem Griff und der Cover-Position. Bewusst kein Listener auf `sun.sun`. Gefahren wird ausschließlich über `cover.set_cover_position`.

### Globale Eingänge und Konstanten

| Was | Wert |
|---|---|
| Anwesenheit | `binary_sensor.anwesenheit_haus` (unklar → „zuhause“) |
| Helligkeit | `sensor.au_gt_sen_light_illuminance`, Schwellen-Helfer (Fallback 40 / 20 lx) |
| Außentemperatur Beschattung | `sensor.rosenthal_temperatur` |
| Sonne | `sun.sun` (elevation, azimuth, next_rising, next_setting) |
| Beschattung | Position 40 %, Elevation ≥ 20°, Temp ≥ 18 °C, an ab 30 000 lx, aus unter 15 000 lx, mind. 600 s zwischen Entscheidungen |
| `PHASE_VORLAUF_MIN` | 120: Handöffnung zählt schon 2 h vor `up_early` als Tagesbeginn |
| `MANUAL_SETTLE` | 90 s nach eigenem Befehl zählt keine Positionsänderung als Handbetrieb |
| Frostschutz | `TEMP_SENSOR = None`, `freeze_temp = None` überall → **toter Code** |

### Je Rollladen (CONFIG)

Bei allen 13 gleich: `open_pos` 100, `closed_pos` 0, Astro-Offset 0, Handsperre 120 min, Blocking 60/60 min, Griff gekippt 25 %. Fallback-Zeiten 07:30 / 09:00 / 19:00 / 22:30.

Unterschiede:

| Rollladen | Griffsensor | Griff offen | Tür | Azimut |
|---|---|---|---|---|
| Abstellkammer | `sensor.hmip_eg_ak_fk` | 80 | | 45–135 |
| Gäste-WC | `sensor.hmip_eg_wc_fk` | 80 | | 315–359 |
| Küche | `sensor.hmip_eg_kz_fk` | 80 | | 45–135 |
| WZ Süden | `sensor.hmip_eg_wz_fk1` | 80 | | 105–230 |
| WZ Essecke | `sensor.hmip_eg_wz_fk2` | 100 | **ja** | 205–270 |
| WZ Terrasse | `sensor.hmip_eg_wz_fk3` | 100 | **ja** | 205–270 |
| WZ Couch | `sensor.hmip_srh_0007d8a99fc532` | 80 | | 205–270 |
| KiZ2 West | `sensor.hmip_og_kiz2_fk1` | 80 | | 205–270 |
| KiZ2 Nord | `sensor.hmip_og_kiz2_fk2` | 80 | | 315–359 |
| Bad | `sensor.hmip_og_bad_fk` | 80 | | 315–359 |
| SZ Süd | `sensor.hmip_og_sz_fk1` | 80 | | 105–230 |
| SZ West | `sensor.hmip_og_sz_fk2` | 80 | | 205–270 |
| KiZ1 | `sensor.hmip_og_kiz1_fk` | 80 | | 105–230 |

### Phase

„auf“ oder „zu“, also was die Automatik gerade will. Reihenfolge: Runterfahrt heute vermerkt → zu; Hochfahrt heute vermerkt → auf; sonst nach Uhrzeit (auf zwischen Morgen- und Abendziel). Die Tages-Merker sind die `letzte_*fahrt`-Helfer, verglichen wird nur das Datum.

### Tagesfahrten

- **Hoch** (nur einmal am Tag, nur wenn Anwesenheitsmodus es erlaubt, läuft **auch bei Handsperre**): erlaubt von `up_early` bis `down_early`, also holt sie nach, wenn HA später startet.
  - `time`: ab `up_early`.
  - `brightness`: sobald Lux ≥ Schwelle hoch, spätestens `up_late` (Zwangsfahrt).
  - `astro`: Sonnenaufgang + Offset, geklemmt in [early, late].
  - Ziel 100 %, oder direkt 40 %, wenn Beschattung schon ansteht.
- **Runter** (einmal am Tag, nicht bei Handsperre, Anwesenheitsmodus): ab `down_early`, sonst analog. Ziel = Griffposition (zu 0 / gekippt 25 / offen 80 bzw. 100).
- Ohne Lux-Wert fährt `brightness` intern wie `astro`.
- Jede Tagesfahrt beendet eine laufende Handsperre und setzt den Tages-Merker, auch wenn der Rollladen schon in Position war.

### Griff (nur Zu-Phase)

Rollladen folgt dem Griff exakt (fährt auch wieder runter). Gilt unabhängig von Anwesenheit und Handsperre, aber mit Blocking-Zeiten. Unavailable zählt als zu (außer bei Türen). In der Auf-Phase wird der Griff ignoriert.

### Tür-Sicherung (Aussperrschutz)

Für Essecke und Terrasse. Sitzt in `_move`, der einzigen Stelle, über die gefahren wird: Ist der Griff nicht `closed`/`tilted` (also auch unavailable), wird **jede Fahrt unter 100 % verweigert**. Tür öffnen → sofort 100 %, egal welche Phase, Sperre oder Blocking. Handfahrten werden nicht zurückgedreht.

### Handbetrieb

Erkennung: Positionsänderung, die nicht zur zuletzt selbst kommandierten Position passt, außerhalb der 90 s Nachlauf. Taster- und Komfortfahrten zählen damit auch als Handbetrieb.

1. Fahrt ganz auf (≥ 100 %) ab Tagesbeginn (`up_early` − 120 min) und vor `down_early`, ohne Hochfahrt heute → Hoch-Merker setzen, Phase auf, keine Sperre.
2. Auf-Phase ohne Beschattung → bleibt stehen, keine Sperre.
3. Fahrt nach unten ab `down_early`, ohne Runterfahrt heute → Runter-Merker setzen, Phase zu, plus Sperre.
4. Sonst (Zu-Phase oder während Beschattung): Beschattung beenden, **Sperre 120 min**. Nach Ablauf und noch Zu-Phase → zurück auf Griffposition (mit Blocking-Prüfung).

### Blocking-Zeiten

60 min vor der frühestmöglichen Morgenfahrt keine Schließfahrt, 60 min vor der Abendfahrt keine Öffnungsfahrt. Gilt für Griff-Reaktion und Rückfahrt nach Sperre, nicht für die Tagesfahrten.

### Beschattung (nur Auf-Phase)

An, wenn alles zutrifft: Beschattungs-Master an, ASC-Master an, Automatik an, Select ≠ off (home/absent mit passender Anwesenheit), Phase auf, keine Handsperre, Griff zu (unavailable zählt als zu), Elevation ≥ 20°, Azimut in [in, out] (**ohne Umlauf über 0°**), Temp ≥ 18 °C, Lux ≥ 30 000. Dann 40 %.
Aus: sofort, wenn eine Grundbedingung wegfällt (zurück auf 100 % in der Auf-Phase); wegen Helligkeit erst unter 15 000 lx oder ohne Lux-Wert. Zwischen zwei Helligkeits-Entscheidungen mind. 600 s.

### Zustand nur im Speicher

Handsperre (`_block_until`), Beschattung aktiv, zuletzt kommandierte Position, Vorposition und Grund liegen **nur im RAM**. Nach einem Neustart von AppDaemon sind laufende Sperren und Beschattung vergessen. Persistent sind nur die Helfer.

## Offene Punkte

- [x] AppDaemon-Quelle liegt vor (`Altsystem/asc_rollladen.py` v0.27). `apps.yaml` fehlt, alle Einstellungen stehen aber in der `.py`.
- [x] Taster-Zuordnung aller 13 Rollläden ausgelesen (Tabelle oben).
- [x] Schuppen und Terrasse: nein, nur Innenrollläden.
- [x] Komfortfunktion Schlafzimmer: bleibt in der Licht-Automation, zählt als Handbetrieb (wie heute).
- [x] Migration: über den Automatik-Schalter je Rollladen, keine Werteübernahme.
- [x] Dashboards geprüft (20.11.), noch nicht angepasst:
  - `dashboard-hardware`, View 16: komplette ASC-Seite (Markdown-Tabelle über `sensor.asc_info_*`, Master/Lux/Beschattung, je Rollladen Auto, Selects, Zeiten, letzte Fahrten; 104 Karten).
  - `dashboard-hausubersicht`: 9 Merker-Kacheln (`input_select.*_merker`) in den Raumabschnitten.

### Entwurfsentscheidungen (20.11.2026, mit Martin)

- [x] **Aufteilung Entities / Optionen** wie unten vorgeschlagen. Wenn etwas nicht passt, wird umgebaut.
- [x] **Handsperre und Beschattung überstehen einen Neustart.**
- [x] **Frostschutz kommt rein, neu gedacht:**
  - Globaler Schalter „Frostschutz“ plus Temperaturschwelle.
  - Liegt die Außentemperatur unter der Schwelle, öffnet die Automatik höchstens auf 10 % (laut Firmware = Lüftungsschlitze ganz offen, Endleiste liegt noch auf) und wartet auf einen Handbefehl.
  - Push „Frostschutz aktiv“ an die gewählten Empfänger. Beim Einrichten Auswahlfeld mit mehreren Empfängern (wie Bewässerung).
  - Noch zu klären: Sensor, Schwelle, was als Handbefehl zählt, Vorrang der Tür-Sicherung (siehe unten).
- [x] **Azimut ohne Umlauf über 0°.** Kein Mehrwert: Bei Elevation ≥ 20° steht die Sonne hier nie im Norden (ca. 280–80°), Nordfenster werden ohnehin nie beschattet.
- [x] **Taster:** kurz im Stillstand → ganz zu, wenn nicht schon zu; ganz zu → auf. Kurz während der Fahrt → Gegenrichtung (zweimal drücken = andere Richtung). Lang → Stopp. Firmware-Befehl 3 „Umschalten“ (Stopp bei Fahrt, sonst Gegenrichtung der letzten Fahrt) passt nicht dazu; die Integration schickt gezielt auf/zu.

### Vorschlag Aufteilung

- **Aufteilung Entities / Optionen:**
  - Entities je Rollladen (täglich verstellbar): Automatik (`switch`), 4 Zeiten (`time`), Fahrmodus hoch/runter, Anwesenheit hoch/runter, Beschattung (`select`); Sensoren Status/Grund, nächste Fahrt hoch/runter, Phase, Sperre bis.
  - Optionen je Rollladen (selten): Cover, Taster, Griffsensor, Tür ja/nein, Griffpositionen, Azimut, Handsperre, Blocking-Zeiten.
  - Anlage: Automatik, Beschattung und Frostschutz (`switch`), Lux-Schwellen und Frostschwelle (`number`) als Entities; Sensoren (Lux, Anwesenheit, Temperatur), Beschattungswerte und Push-Empfänger in den Optionen.

### Frostschutz

Entschieden:
- [x] Temperatur: `sensor.rosenthal_temperatur` (wie Beschattung).
- [x] Jede Handfahrt (Taster, Dashboard, …) gilt als Handbefehl. Danach normaler Betrieb für diesen Rollladen bis zum nächsten Tag.
- [x] Nässeprüfung: Ohne Nässe friert nichts fest, dann läuft alles normal.

Verfügbare Wetterdaten (Station Rosenthal, Plattform `scrape`, Aktualisierung etwa alle 15–60 min): Temperatur, Luftfeuchte, Taupunkt, Niederschlag 1 h / heute, Regenrate, Bodentemperatur 5 cm. Am 20.11. 06:13: 3,6 °C, 95 % Feuchte.

Vorschlag Logik:
- **Kalt:** Temperatur unter Schwelle (Standard 1,5 °C, einstellbar), aus erst 1 K darüber.
- **Nass:** Niederschlag in den letzten N Stunden (Standard 24 h, einstellbar). Die Integration merkt sich den letzten Niederschlag selbst (aus „Niederschlag 1h“) und speichert ihn über Neustarts.
- **Luftfeuchte nur in Kombination mit der Temperatur:** Plusgrade und hohe Feuchte in den letzten N Stunden (Variante B, siehe unten). Allein nicht: Im Winter liegt sie fast immer über 90 %, der Frostschutz wäre sonst praktisch dauernd aktiv.
- **Fällt der Niederschlagssensor aus** → als nass werten (im Zweifel vorsichtig).
- Risiko Schnee: Ein unbeheizter Regenmesser zählt Schnee erst beim Tauen. Optional zusätzlich eine `weather`-Entity (z. B. DWD) auswerten: Zustand `snowy`, `snowy-rainy`, `rainy`, `pouring`, `hail` in den letzten N Stunden = nass.
- Frostschutz aktiv = Schalter an UND kalt UND nass.

- [x] 10-%-Grenze gilt für **alle** automatischen Öffnungen: Morgenfahrt, Griff (gekippt/offen), Rückfahrt nach Handsperre.
- [x] Frostschutz je Rollladen abschaltbar (Option „Frostschutz“). WZ Essecke und WZ Terrasse aus (unter dem Terrassendach). Damit kein Konflikt mit der Tür-Sicherung.
- [x] Luftfeuchte allein ist kein Nässe-Kriterium, nur zusammen mit der Temperatur.

- [x] **Feuchte + Temperatur (Variante B, „erst nass im Plus, dann Frost“):** Nass gilt auch, wenn in den letzten N Stunden die Temperatur über 0 °C und gleichzeitig die Luftfeuchte über einer Schwelle lag (Standard 90 %, einstellbar). Niederschlag in den letzten N Stunden zählt weiterhin.
- [x] **Notbetrieb geht vor.** Die Integration fasst den Notbetrieb der Module nicht an, auch nicht bei Frost. Fällt HA aus, soll der Rollladen auffahren; Frost ist selten.

### Firmware (HBW-MB-Bl v1.08)

Vorhanden und ausreichend: Position, Status (zu/offen/öffnet/schließt), Position bekannt, Zwischenfahrten mit automatischer Referenzfahrt, Notbetrieb je Rollladen. Nichts davon fehlt der Integration.

- Ein angefrorener Rollladen ist im Modul nicht erkennbar (nur Relais, keine Strommessung, Position nach Zeit). Der Frostschutz muss deshalb über die Temperatur laufen.
- Notbetrieb „auf“ öffnet auch bei Frost ganz. Gewollt, keine Änderung (Entscheidung 20.11.).
- Notbetrieb der Tür-Rollläden (WZ Essecke, WZ Terrasse) darf nie „zu“ sein. **Prüfen.**
- Nice to have: Zielposition einer laufenden Fahrt als Input-Register.
- [x] Name: Domain `rollladen`, Repo `Efka00/ha-rollladen` (Projektordner heißt noch `Rolladen`).
