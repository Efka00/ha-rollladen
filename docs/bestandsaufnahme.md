# Bestandsaufnahme Altsystem (Stand 19.11.2026)

Aus HA ausgelesen (ha-mcp). Die AppDaemon-Quelle der Rollladenautomatik („ASC“) liegt **noch nicht vor**.

## Ziel (19.11.2026, mit Martin)

- **Alles in eine Integration.** Keine Helfer, keine Blueprints, keine Rollladen-Automationen mehr. Updates über den Marketplace.
- Vorbild ist die Integration Bewässerung (`Efka00/ha-bewaesserung`): Hub mit `single_config_entry`, ein Gerät je Rollladen, Einstellungen als Entities, Optionsmenü zum Hinzufügen und Bearbeiten.
- **Nur die 13 Innenrollläden.** Schuppen und Terrasse bleiben bei ihren Automationen.
- **Komfortfunktion Schlafzimmer bleibt draußen** (in `og_schlafzimmer_beleuchtung`). Die Integration muss deren `close_cover` als Fremdfahrt erkennen. Ob das als Handbetrieb zählt, klärt sich mit der ASC-Quelle.
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
| `cover.eg_kz_ro` | Küche | A05/3 | ? | Küche |
| `cover.eg_wc_ro` | Gäste-WC | A05/4 | ? | Gäste-WC |
| `cover.eg_wz_ro1` | WZ Süden | A05/1 | `event.hmipw_e02_eg_wz_tt1_s1` | Wohnzimmer |
| `cover.eg_wz_ro2` | WZ Essecke | A06/2 | ? | Wohnzimmer |
| `cover.eg_wz_ro3` | WZ Terrasse | A06/3 | ? | Wohnzimmer |
| `cover.eg_wz_ro4` | WZ Couch | A06/4 | ? | Wohnzimmer |
| `cover.og_bad_ro` | Bad | A10 | ? | Badezimmer |
| `cover.og_kiz1_ro` | KiZ1 | A06/1 | ? | KiZ1 |
| `cover.og_kiz2_ro1` | KiZ2 West | A07/2 | `event.hmipw_e03_og_kiz2_tt_s1` | Ankleide |
| `cover.og_kiz2_ro2` | KiZ2 Nord | A07/3 | ? | Ankleide |
| `cover.og_sz_ro1` | SZ Süd | A07/4 | `event.hmipw_e02_og_sz_tt_s2` | Schlafzimmer |
| `cover.og_sz_ro2` | SZ West | A07/1 | ? | Schlafzimmer |

`?` = Automation noch nicht im Detail gelesen. Alle Taster sind HmIP-Wired über `homematicip_local`, Events `press_short` / `press_long`.

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
| `input_datetime.…_letzte_hochfahrt` / `_runterfahrt` | Statistik |
| `sensor.asc_info_<name>` | von AppDaemon, Attribute siehe unten |

Summe: 4 global + 13 × 8 Helfer = **108 Helfer**, dazu 13 AppDaemon-Sensoren und 16 Automationen.

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

Daraus ablesbar, ohne Quelle zu kennen:
- Betriebsart je Richtung (`brightness`, vermutlich auch `time`), Zeitfenster früh/spät, Zwangsfahrt bei Spätzeit.
- Anwesenheitsregel je Richtung.
- Fenstergriff-Sperre (`griff`), Tür-Sperre (Aussperrschutz), allgemeine Sperre, `blocking`.
- Beschattung mit Grund.
- Phasenmodell (auf/zu) mit Handbetrieb-Erkennung: Wird von Hand gefahren, bleibt die Position bis zur nächsten Phase.

## Offene Punkte

- [ ] AppDaemon-Quelle (`asc*.py` + `apps.yaml`) ins Projekt legen (kommt 20.11.).
- [ ] Taster-Zuordnung der übrigen 9 Rollläden auslesen.
- [x] Schuppen und Terrasse: nein, nur Innenrollläden.
- [x] Komfortfunktion Schlafzimmer: bleibt in der Licht-Automation. Offen: zählt die Fahrt als Handbetrieb?
- [x] Migration: über den Automatik-Schalter je Rollladen, keine Werteübernahme.
- [ ] Dashboards prüfen, die Merker, ASC-Helfer oder `sensor.asc_info_*` zeigen.
- [ ] Name: Domain `rollladen`, Repo `ha-rollladen`? (Projektordner heißt noch `Rolladen`.)
