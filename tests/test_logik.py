"""Tests der Entscheidungslogik, ohne Home Assistant.

Lokal:  python3 -m unittest discover -s tests -v
CI:     pytest (findet die unittest-Klassen ebenfalls)

logik.py wird direkt über den Dateipfad geladen, damit das Paket (und damit
Home Assistant) nicht importiert wird.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

_PFAD = Path(__file__).resolve().parents[1] / "custom_components" / "rollladen" / "logik.py"
_spec = importlib.util.spec_from_file_location("rollladen_logik", _PFAD)
L = importlib.util.module_from_spec(_spec)
sys.modules["rollladen_logik"] = L
_spec.loader.exec_module(L)

TZ = ZoneInfo("Europe/Berlin")


def dt(h: int, m: int = 0, tag: int = 20) -> datetime:
    return datetime(2026, 11, tag, h, m, tzinfo=TZ)


class Fake:
    """Umgebung zum Testen: alles direkt setzbar, Fahrbefehle werden notiert."""

    def __init__(self) -> None:
        self.zeit = dt(6, 0)
        self.auto = True
        self.beschattung = False
        self.frost = False
        self.lux_wert: float | None = 0
        self.hoch = 700.0
        self.runter = 600.0
        self.da = True
        self.temp: float | None = 10
        self.sonne_wert: tuple[float, float] | None = (10, 180)
        self.sonnenaufgang = time(7, 45)
        self.sonnenuntergang = time(16, 30)
        self.griffe: dict[str, str | None] = {}
        self.positionen: dict[str, int | None] = {}
        self.fahrten: list[tuple[str, int]] = []
        self.frost_meldungen: list[str] = []

    # Umgebung
    def jetzt(self): return self.zeit
    def automatik(self): return self.auto
    def beschattung_an(self): return self.beschattung
    def frost_aktiv(self): return self.frost
    def lux(self): return self.lux_wert
    def lux_hoch(self): return self.hoch
    def lux_runter(self): return self.runter
    def jemand_da(self): return self.da
    def temperatur(self): return self.temp
    def sonne(self): return self.sonne_wert

    def astro(self, richtung, tag: date):
        t = self.sonnenaufgang if richtung == L.HOCH else self.sonnenuntergang
        return datetime.combine(tag, t, tzinfo=TZ)

    def griff(self, r): return self.griffe.get(r.id)
    def position(self, r): return self.positionen.get(r.id)

    def fahre(self, r, pos):
        self.fahrten.append((r.id, pos))
        self.positionen[r.id] = pos      # Cover folgt sofort

    def frost_begrenzt(self, r): self.frost_meldungen.append(r.name)
    def log(self, r, text): pass


def rollladen(**kwargs) -> L.Rollladen:
    s = {"automatik": True}
    s.update(kwargs.pop("s", {}))
    return L.Rollladen("r1", "Test", "cover.test", s, **kwargs)


class Basis(unittest.TestCase):
    def setUp(self) -> None:
        self.u = Fake()
        self.rech = L.Rechner(self.u, L.Global())

    def neu(self, pos: int = 0, **kwargs) -> L.Rollladen:
        r = rollladen(**kwargs)
        self.u.positionen[r.id] = pos
        return r

    def hand(self, r: L.Rollladen, pos: int) -> None:
        """Fremde Fahrt: Position ändert sich ohne eigenen Befehl."""
        alt = self.u.positionen.get(r.id)
        self.u.positionen[r.id] = pos
        self.rech.position_geaendert(r, pos, alt)


class TestTagesfahrten(Basis):
    def test_morgens_helligkeit(self) -> None:
        r = self.neu(0)
        self.u.zeit = dt(7, 0)
        self.u.lux_wert = 900
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [], "vor hoch_frueh keine Fahrt")
        self.u.zeit = dt(7, 40)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 100)])
        self.assertEqual(self.rech.phase(r), L.AUF)
        self.rech.bewerte(r)
        self.assertEqual(len(self.u.fahrten), 1, "nur einmal am Tag")

    def test_zwangsfahrt_spaetzeit(self) -> None:
        r = self.neu(0)
        self.u.lux_wert = 100
        self.u.zeit = dt(8, 59)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [])
        self.u.zeit = dt(9, 0)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 100)])
        self.assertIn("Zwangsfahrt", r.grund)

    def test_ohne_lux_wie_astro(self) -> None:
        r = self.neu(0)
        self.u.lux_wert = None
        self.u.zeit = dt(7, 44)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [])
        self.u.zeit = dt(7, 45)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 100)])
        self.assertIn("Lux-Ersatz", r.grund)

    def test_abends_auf_griffposition(self) -> None:
        r = self.neu(100, griff="sensor.griff",
                     s={"letzte_hoch": dt(7, 40).isoformat()})
        self.u.griffe["r1"] = L.GRIFF_GEKIPPT
        self.u.zeit = dt(19, 30)
        self.u.lux_wert = 10
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 25)])
        self.assertEqual(self.rech.phase(r), L.ZU)

    def test_zeitmodus_und_astro_klemmung(self) -> None:
        r = self.neu(100, s={"fahrmodus_runter": L.FM_ASTRO,
                             "letzte_hoch": dt(7, 40).isoformat()})
        # Sonnenuntergang 16:30 liegt vor runter_frueh 19:00 -> 19:00
        self.assertEqual(self.rech.zielzeit(r, L.RUNTER, dt(0).date()), dt(19, 0))
        self.u.zeit = dt(18, 59)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [])
        self.u.zeit = dt(19, 0)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 0)])

    def test_anwesenheit(self) -> None:
        r = self.neu(0, s={"anwesenheit_hoch": L.AW_ABWESEND})
        self.u.zeit = dt(9, 0)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [], "jemand da -> keine Fahrt")
        self.u.da = False
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 100)])

    def test_automatik_aus(self) -> None:
        r = self.neu(0, s={"automatik": False})
        self.u.zeit = dt(9, 0)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [])

    def test_phase_nach_uhrzeit(self) -> None:
        r = self.neu(0, s={"fahrmodus_hoch": L.FM_ZEIT, "fahrmodus_runter": L.FM_ZEIT})
        self.u.zeit = dt(12, 0)
        self.assertEqual(self.rech.phase(r), L.AUF)
        self.u.zeit = dt(20, 0)
        self.assertEqual(self.rech.phase(r), L.ZU)


class TestHandbetrieb(Basis):
    def test_sperre_und_rueckfahrt(self) -> None:
        r = self.neu(0, s={"letzte_runter": dt(19, 0).isoformat()})
        self.u.zeit = dt(21, 0)
        self.hand(r, 60)
        self.assertTrue(self.rech.gesperrt(r))
        self.u.zeit = dt(22, 59)
        self.rech.sperre_pruefen(r)
        self.assertEqual(self.u.fahrten, [])
        self.u.zeit = dt(23, 1)
        self.rech.sperre_pruefen(r)
        self.assertEqual(self.u.fahrten, [("r1", 0)])
        self.assertFalse(self.rech.gesperrt(r))

    def test_handoeffnung_setzt_auf_phase(self) -> None:
        r = self.neu(0)
        self.u.zeit = dt(6, 30)          # vor hoch_frueh, nach Tagesbeginn
        self.hand(r, 100)
        self.assertTrue(self.rech.gefahren_heute(r, L.HOCH))
        self.assertEqual(self.rech.phase(r), L.AUF)
        self.assertFalse(self.rech.gesperrt(r))

    def test_anheben_setzt_keine_phase(self) -> None:
        r = self.neu(0)
        self.u.zeit = dt(6, 30)
        self.hand(r, 15)
        self.assertFalse(self.rech.gefahren_heute(r, L.HOCH))
        self.assertTrue(self.rech.gesperrt(r))

    def test_eigene_fahrt_ist_kein_handbetrieb(self) -> None:
        r = self.neu(0)
        self.u.zeit = dt(9, 0)
        self.rech.bewerte(r)                 # fährt auf 100
        self.rech.position_geaendert(r, 50, 0)   # Zwischenwert in der Fahrt
        self.assertFalse(self.rech.gesperrt(r))
        self.assertEqual(r.grund, "Zwangsfahrt (Spätzeit)")

    def test_taster_wird_immer_erkannt(self) -> None:
        r = self.neu(0, s={"letzte_runter": dt(19, 0).isoformat()})
        self.u.zeit = dt(21, 0)
        self.rech.bewege(r, 0, "test")        # frischer eigener Befehl
        self.rech.taster_gedrueckt(r)
        self.hand(r, 100)
        self.assertTrue(self.rech.gesperrt(r))

    def test_handschliessung_abends_setzt_zu_phase(self) -> None:
        r = self.neu(100, s={"letzte_hoch": dt(7, 40).isoformat()})
        self.u.zeit = dt(19, 30)
        self.hand(r, 0)
        self.assertTrue(self.rech.gefahren_heute(r, L.RUNTER))
        self.assertEqual(self.rech.phase(r), L.ZU)
        self.assertTrue(self.rech.gesperrt(r))


class TestGriffUndTuer(Basis):
    def test_griff_nur_in_zu_phase(self) -> None:
        r = self.neu(0, griff="sensor.griff",
                     s={"letzte_runter": dt(19, 0).isoformat()})
        self.u.zeit = dt(21, 0)
        self.u.griffe["r1"] = L.GRIFF_OFFEN
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten, [("r1", 80)])
        self.u.griffe["r1"] = L.GRIFF_ZU
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten[-1], ("r1", 0))

    def test_griff_in_auf_phase_ignoriert(self) -> None:
        r = self.neu(100, griff="sensor.griff",
                     s={"letzte_hoch": dt(7, 40).isoformat()})
        self.u.zeit = dt(12, 0)
        self.u.griffe["r1"] = L.GRIFF_GEKIPPT
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten, [])

    def test_tuer_auf_faehrt_immer_hoch(self) -> None:
        r = self.neu(0, griff="sensor.griff", tuer=True,
                     s={"letzte_runter": dt(19, 0).isoformat()})
        self.u.zeit = dt(21, 0)
        self.hand(r, 30)                     # Sperre aktiv
        self.u.griffe["r1"] = L.GRIFF_OFFEN
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten, [("r1", 100)])

    def test_tuer_offen_blockiert_schliessen(self) -> None:
        r = self.neu(100, griff="sensor.griff", tuer=True,
                     s={"letzte_hoch": dt(7, 40).isoformat()})
        self.u.griffe["r1"] = L.GRIFF_OFFEN
        self.u.zeit = dt(19, 30)
        self.u.lux_wert = 10
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [])
        self.assertIn("blockiert", r.grund)

    def test_tuer_griff_unbekannt_blockiert(self) -> None:
        r = self.neu(100, griff="sensor.griff", tuer=True)
        self.u.griffe["r1"] = None
        self.assertFalse(self.rech.bewege(r, 0, "test"))

    def test_blocking_vor_morgenfahrt(self) -> None:
        r = self.neu(80, griff="sensor.griff",
                     s={"letzte_runter": dt(19, 0, tag=19).isoformat()})
        self.u.zeit = dt(7, 0)               # 30 min vor hoch_frueh
        self.u.griffe["r1"] = L.GRIFF_ZU
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten, [], "Schließen vor Morgenfahrt blockiert")


class TestBeschattung(Basis):
    def setUp(self) -> None:
        super().setUp()
        self.u.beschattung = True
        self.u.temp = 25
        self.u.sonne_wert = (40, 180)
        self.u.zeit = dt(12, 0)

    def neu_b(self) -> L.Rollladen:
        return self.neu(100, azimut_von=105, azimut_bis=230,
                        s={"beschattung": L.BS_IMMER,
                           "letzte_hoch": dt(7, 40).isoformat()})

    def test_an_und_aus_mit_hysterese(self) -> None:
        r = self.neu_b()
        self.u.lux_wert = 35000
        self.rech.beschattung_pruefen(r)
        self.assertEqual(self.u.fahrten, [("r1", 40)])
        self.assertTrue(r.beschattet)
        self.u.zeit += timedelta(minutes=11)
        self.u.lux_wert = 20000              # zwischen den Schwellen: bleibt
        self.rech.beschattung_pruefen(r)
        self.assertTrue(r.beschattet)
        self.u.lux_wert = 10000
        self.rech.beschattung_pruefen(r)
        self.assertFalse(r.beschattet)
        self.assertEqual(self.u.fahrten[-1], ("r1", 100))

    def test_wartezeit(self) -> None:
        r = self.neu_b()
        self.u.lux_wert = 35000
        self.rech.beschattung_pruefen(r)
        self.u.zeit += timedelta(minutes=5)
        self.u.lux_wert = 1000
        self.rech.beschattung_pruefen(r)
        self.assertTrue(r.beschattet, "innerhalb der Wartezeit keine Änderung")

    def test_grundbedingung_weg_sofort(self) -> None:
        r = self.neu_b()
        self.u.lux_wert = 35000
        self.rech.beschattung_pruefen(r)
        self.u.zeit += timedelta(minutes=1)
        self.u.sonne_wert = (40, 260)        # Azimut raus
        self.rech.beschattung_pruefen(r)
        self.assertFalse(r.beschattet)
        self.assertEqual(self.u.fahrten[-1], ("r1", 100))

    def test_morgenfahrt_direkt_in_beschattung(self) -> None:
        r = self.neu(0, azimut_von=105, azimut_bis=230,
                     s={"beschattung": L.BS_IMMER})
        self.u.zeit = dt(8, 0)
        self.u.lux_wert = 35000
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 40)])
        self.assertTrue(r.beschattet)

    def test_ohne_azimut_nie(self) -> None:
        r = self.neu(100, s={"beschattung": L.BS_IMMER,
                             "letzte_hoch": dt(7, 40).isoformat()})
        self.u.lux_wert = 35000
        self.rech.beschattung_pruefen(r)
        self.assertEqual(self.u.fahrten, [])


class TestFrostschutz(Basis):
    def test_morgens_nur_frostposition(self) -> None:
        self.u.frost = True
        r = self.neu(0)
        self.u.zeit = dt(9, 0)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 10)])
        self.assertEqual(self.u.frost_meldungen, ["Test"])
        self.assertTrue(self.rech.gefahren_heute(r, L.HOCH))

    def test_handfahrt_gibt_frei(self) -> None:
        self.u.frost = True
        r = self.neu(0, griff="sensor.griff")
        self.u.zeit = dt(9, 0)
        self.rech.bewerte(r)
        self.u.zeit = dt(9, 5)
        self.hand(r, 100)
        self.assertFalse(self.rech.frost_greift(r))
        # Abends, Fenster offen -> 80 % ohne Begrenzung
        self.u.zeit = dt(21, 0)
        self.u.lux_wert = 0
        self.rech.bewerte(r)                       # Abendfahrt -> 0
        self.u.griffe["r1"] = L.GRIFF_OFFEN
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten[-1], ("r1", 80))

    def test_griff_begrenzt(self) -> None:
        self.u.frost = True
        r = self.neu(0, griff="sensor.griff",
                     s={"letzte_runter": dt(19, 0).isoformat()})
        self.u.zeit = dt(21, 0)
        self.u.griffe["r1"] = L.GRIFF_GEKIPPT
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten, [("r1", 10)])

    def test_tuer_sicherheit_hat_vorrang(self) -> None:
        self.u.frost = True
        r = self.neu(0, griff="sensor.griff", tuer=True,
                     s={"letzte_runter": dt(19, 0).isoformat()})
        self.u.zeit = dt(21, 0)
        self.u.griffe["r1"] = L.GRIFF_OFFEN
        self.rech.griff_geaendert(r)
        self.assertEqual(self.u.fahrten, [("r1", 100)])

    def test_rollladen_ohne_frostschutz(self) -> None:
        self.u.frost = True
        r = self.neu(0, frostschutz=False)
        self.u.zeit = dt(9, 0)
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 100)])

    def test_schliessen_unbegrenzt(self) -> None:
        self.u.frost = True
        r = self.neu(100, s={"letzte_hoch": dt(7, 40).isoformat()})
        self.u.zeit = dt(19, 30)
        self.u.lux_wert = 10
        self.rech.bewerte(r)
        self.assertEqual(self.u.fahrten, [("r1", 0)])


class TestFrostBewertung(unittest.TestCase):
    def bewerte(self, f, jetzt, **kw):
        args = dict(temp=0.0, schwelle=1.5, hysterese=1.0, stunden=24,
                    niederschlag_quelle=True, niederschlag=0.0,
                    feuchte_quelle=True, feuchte=80.0, feuchte_schwelle=90,
                    wetter_quelle=False, wetter=None)
        args.update(kw)
        L.frost_bewerten(f, jetzt, **args)
        return f

    def test_kalt_mit_hysterese(self) -> None:
        f = self.bewerte({}, dt(6), temp=1.0)
        self.assertTrue(f["kalt"])
        self.bewerte(f, dt(7), temp=2.4)
        self.assertTrue(f["kalt"], "bleibt bis Schwelle + Hysterese")
        self.bewerte(f, dt(8), temp=2.6)
        self.assertFalse(f["kalt"])

    def test_trocken_kein_frost(self) -> None:
        f = self.bewerte({}, dt(6))
        self.assertTrue(f["kalt"])
        self.assertFalse(f["nass"])

    def test_niederschlag_zaehlt_stunden(self) -> None:
        f = self.bewerte({}, dt(6, tag=19), niederschlag=0.4)
        self.assertTrue(f["nass"])
        self.bewerte(f, dt(5, tag=20), niederschlag=0.0)
        self.assertTrue(f["nass"], "23 h später noch nass")
        self.bewerte(f, dt(7, tag=20), niederschlag=0.0)
        self.assertFalse(f["nass"], "nach 25 h trocken")

    def test_feuchte_nur_bei_plusgraden(self) -> None:
        f = self.bewerte({}, dt(6), temp=-1.0, feuchte=98.0)
        self.assertFalse(f["nass"], "Feuchte im Frost allein zählt nicht")
        self.bewerte(f, dt(7), temp=3.0, feuchte=95.0)
        self.assertTrue(f["nass"])
        self.assertFalse(f["kalt"])
        self.bewerte(f, dt(12), temp=0.5, feuchte=95.0)
        self.assertTrue(f["kalt"] and f["nass"], "erst nass im Plus, dann Frost")

    def test_sensor_weg_gilt_nass(self) -> None:
        f = self.bewerte({}, dt(6), niederschlag=None)
        self.assertTrue(f["nass"])

    def test_ohne_quelle_nur_temperatur(self) -> None:
        f = self.bewerte({}, dt(6), niederschlag_quelle=False, feuchte_quelle=False)
        self.assertTrue(f["nass"])

    def test_wetter_schnee(self) -> None:
        f = self.bewerte({}, dt(6), wetter_quelle=True, wetter="snowy")
        self.assertTrue(f["nass"])

    def test_temperatur_weg_behaelt_zustand(self) -> None:
        f = self.bewerte({}, dt(6), temp=0.0)
        self.bewerte(f, dt(7), temp=None)
        self.assertTrue(f["kalt"])


class TestTaster(unittest.TestCase):
    def test_regeln(self) -> None:
        self.assertEqual(L.taster_aktion(True, "open", 100), "stopp")
        self.assertEqual(L.taster_aktion(False, "closed", 0), "auf")
        self.assertEqual(L.taster_aktion(False, "open", 100), "zu")
        self.assertEqual(L.taster_aktion(False, "open", 25), "zu",
                         "Zwischenposition -> runter")
        self.assertEqual(L.taster_aktion(False, "opening", 40), "zu",
                         "während der Fahrt -> Gegenrichtung")
        self.assertEqual(L.taster_aktion(False, "closing", 40), "auf")
        self.assertEqual(L.taster_aktion(False, "closed", None), "auf")


if __name__ == "__main__":
    unittest.main()
