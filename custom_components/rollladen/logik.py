"""Entscheidungslogik der Rollläden, ohne Home Assistant.

Port der AppDaemon-App ASC (asc_rollladen.py v0.27), ergänzt um
Frostschutz und Taster. Die Datei importiert nichts aus Home Assistant und
nichts aus dem Paket, damit sie sich ohne HA testen lässt. Den Zugriff auf
Zustände und das Fahren übernimmt eine Umgebung (siehe ``Umgebung``).

Phase („auf“ / „zu“) = was die Automatik gerade will:
  1. Runterfahrt heute vermerkt  -> zu
  2. Hochfahrt heute vermerkt    -> auf
  3. sonst nach Uhrzeit: auf zwischen Morgen- und Abendziel

Tagesfahrten
  Hoch:   einmal am Tag, ab up_early bis down_early, läuft auch bei
          Handsperre. Ziel 100 % (oder gleich Beschattungsposition).
  Runter: einmal am Tag ab down_early, nicht bei Handsperre. Ziel ist die
          Griffposition (zu / gekippt / offen).
  Fahrmodus je Richtung: Zeit, Helligkeit (Zwangsfahrt zur Spätzeit),
  Astro (geklemmt ins Zeitfenster). Ohne Lux-Wert fährt Helligkeit wie
  Astro.

Griff (nur Zu-Phase): Rollladen folgt dem Griff exakt.
Tür-Sicherung: bei offenem (oder unbekanntem) Griff keine Fahrt unter
  100 %; Tür öffnen fährt sofort auf 100 %.
Handbetrieb: Positionsänderung, die nicht zum eigenen Befehl passt. In der
  Zu-Phase (oder während der Beschattung) Sperre, danach Rückfahrt.
  Ganz auf am Tag setzt die Auf-Phase, zu am Abend die Zu-Phase.
Blocking-Zeiten: vor der Morgenfahrt kein Schließen, vor der Abendfahrt
  kein Öffnen (gilt für Griff und Rückfahrt, nicht für Tagesfahrten).
Beschattung (nur Auf-Phase): Sonne im Azimut, hoch genug, warm, hell.
  Hysterese über zwei Lux-Schwellen und Mindestabstand.
Frostschutz: Ist er aktiv, öffnet die Automatik höchstens bis zur
  Frostposition und wartet auf einen Handbefehl. Jede Handfahrt gibt den
  Rollladen bis zum Tagesende frei. Die Tür-Sicherung hat Vorrang.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Protocol

AUF = "auf"
ZU = "zu"
HOCH = "hoch"
RUNTER = "runter"

# Fahrmodi
FM_ZEIT = "Zeit"
FM_HELLIGKEIT = "Helligkeit"
FM_ASTRO = "Astro"
FAHRMODI = [FM_ZEIT, FM_HELLIGKEIT, FM_ASTRO]

# Anwesenheitsmodi der Tagesfahrten
AW_IMMER = "Immer"
AW_ABWESEND = "Nur wenn niemand da ist"
AW_AUS = "Aus"
ANWESENHEIT = [AW_IMMER, AW_ABWESEND, AW_AUS]

# Beschattungsmodi
BS_AUS = "Aus"
BS_IMMER = "Immer"
BS_ANWESEND = "Nur wenn jemand da ist"
BS_ABWESEND = "Nur wenn niemand da ist"
BESCHATTUNG = [BS_AUS, BS_IMMER, BS_ANWESEND, BS_ABWESEND]

# Zustände eines Fenstergriffs (HmIP-SRH)
GRIFF_ZU = "closed"
GRIFF_GEKIPPT = "tilted"
GRIFF_OFFEN = "open"

OFFEN_POS = 100
ZU_POS = 0

# Wie viele Minuten VOR up_early eine Handöffnung schon als Tagesbeginn zählt.
PHASE_VORLAUF_MIN = 120
# So lange nach einem eigenen Befehl zählt eine Positionsänderung nicht als
# Handbetrieb (Fahrzeit, Zwischenwerte).
MANUAL_SETTLE_S = 90

# Zeitfenster je Rollladen (Schlüssel im Speicher)
ZEITEN = ("hoch_frueh", "hoch_spaet", "runter_frueh", "runter_spaet")

SPEICHER_DEFAULTS: dict[str, Any] = {
    "automatik": False,
    "hoch_frueh": "07:30:00",
    "hoch_spaet": "09:00:00",
    "runter_frueh": "19:00:00",
    "runter_spaet": "22:30:00",
    "fahrmodus_hoch": FM_HELLIGKEIT,
    "fahrmodus_runter": FM_HELLIGKEIT,
    "anwesenheit_hoch": AW_IMMER,
    "anwesenheit_runter": AW_IMMER,
    "beschattung": BS_AUS,
    # Zustand
    "letzte_hoch": None,        # ISO-Zeitpunkt = Tages-Merker
    "letzte_runter": None,
    "sperre_bis": None,
    "beschattet": False,
    "beschattung_zuletzt": None,
    "soll_pos": None,           # zuletzt selbst kommandierte Position
    "soll_zeit": None,
    "frost_frei": None,         # Datum, an dem eine Handfahrt freigegeben hat
    "letzte_pos": None,
    "grund": "–",
}


# ----------------------------------------------------------------------
#  Hilfen
# ----------------------------------------------------------------------

def iso(wert: datetime | None) -> str | None:
    return wert.isoformat() if wert is not None else None


def aus_iso(wert: Any) -> datetime | None:
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert))
    except ValueError:
        return None


def uhrzeit(wert: Any, ersatz: str) -> time:
    try:
        return time.fromisoformat(str(wert))
    except ValueError:
        return time.fromisoformat(ersatz)


def als_int(wert: Any) -> int | None:
    if wert in (None, "", "unavailable", "unknown"):
        return None
    try:
        return int(round(float(wert)))
    except (TypeError, ValueError):
        return None


def taster_aktion(lang: bool, status: str | None, position: int | None) -> str:
    """Was ein Tastendruck bewirkt: 'auf', 'zu' oder 'stopp'.

    Lang = Stopp. Kurz während der Fahrt = Gegenrichtung (zweimal drücken =
    andere Richtung). Kurz im Stillstand: ganz zu -> auf, sonst -> zu.
    """
    if lang:
        return "stopp"
    if status == "opening":
        return "zu"
    if status == "closing":
        return "auf"
    if position == 0 or (position is None and status == "closed"):
        return "auf"
    return "zu"


# ----------------------------------------------------------------------
#  Konfiguration
# ----------------------------------------------------------------------

@dataclass
class Global:
    """Anlagenweite Werte aus den Optionen."""

    beschattung_pos: int = 40
    min_elevation: float = 20
    min_temp: float = 18
    sonnig: float = 30000
    bewoelkt: float = 15000
    wartezeit_s: float = 600
    frost_pos: int = 10


class Rollladen:
    """Ein Rollladen: Einstellungen aus dem Dialog + gespeicherter Zustand."""

    def __init__(self, rid: str, name: str, cover: str, s: dict[str, Any], *,
                 taster: list[str] | None = None,
                 taster_kurz: str = "press_short",
                 taster_lang: str = "press_long",
                 griff: str | None = None,
                 tuer: bool = False,
                 gekippt_pos: int = 25,
                 griff_offen_pos: int = 80,
                 azimut_von: float | None = None,
                 azimut_bis: float | None = None,
                 sperre_min: int = 120,
                 block_morgen: int = 60,
                 block_abend: int = 60,
                 frostschutz: bool = True) -> None:
        self.id = rid
        self.name = name
        self.cover = cover
        self.taster = list(taster or [])
        self.taster_kurz = taster_kurz
        self.taster_lang = taster_lang
        self.griff = griff
        self.tuer = tuer
        self.gekippt_pos = int(gekippt_pos)
        self.griff_offen_pos = int(griff_offen_pos)
        self.azimut_von = azimut_von
        self.azimut_bis = azimut_bis
        self.sperre_min = int(sperre_min)
        self.block_morgen = int(block_morgen)
        self.block_abend = int(block_abend)
        self.frostschutz = frostschutz
        for key, wert in SPEICHER_DEFAULTS.items():
            s.setdefault(key, wert)
        self.s = s

    @property
    def beschattbar(self) -> bool:
        return self.azimut_von is not None and self.azimut_bis is not None

    def zeit(self, key: str) -> time:
        return uhrzeit(self.s.get(key), SPEICHER_DEFAULTS[key])

    @property
    def automatik(self) -> bool:
        return bool(self.s["automatik"])

    @property
    def beschattet(self) -> bool:
        return bool(self.s["beschattet"])

    @property
    def grund(self) -> str:
        return str(self.s.get("grund") or "–")


class Umgebung(Protocol):
    """Was die Logik von Home Assistant braucht."""

    def jetzt(self) -> datetime: ...
    def automatik(self) -> bool: ...
    def beschattung_an(self) -> bool: ...
    def frost_aktiv(self) -> bool: ...
    def lux(self) -> float | None: ...
    def lux_hoch(self) -> float: ...
    def lux_runter(self) -> float: ...
    def jemand_da(self) -> bool: ...
    def temperatur(self) -> float | None: ...
    def sonne(self) -> tuple[float, float] | None: ...
    def astro(self, richtung: str, tag: date) -> datetime | None: ...
    def griff(self, r: Rollladen) -> str | None: ...
    def position(self, r: Rollladen) -> int | None: ...
    def fahre(self, r: Rollladen, pos: int) -> None: ...
    def frost_begrenzt(self, r: Rollladen) -> None: ...
    def log(self, r: Rollladen, text: str) -> None: ...


# ----------------------------------------------------------------------
#  Rechner
# ----------------------------------------------------------------------

class Rechner:
    """Alle Entscheidungen für die Rollläden. Hält selbst keinen Zustand,
    der liegt in ``Rollladen.s``."""

    def __init__(self, umg: Umgebung, glob: Global) -> None:
        self.u = umg
        self.g = glob

    # ---- Grundlagen ---------------------------------------------------

    def _kombi(self, tag: date, t: time) -> datetime:
        return datetime.combine(tag, t, tzinfo=self.u.jetzt().tzinfo)

    def aktiv(self, r: Rollladen) -> bool:
        return self.u.automatik() and r.automatik

    def gefahren_heute(self, r: Rollladen, richtung: str) -> bool:
        wann = aus_iso(r.s["letzte_" + richtung])
        return wann is not None and wann.date() == self.u.jetzt().date()

    def _stempel(self, r: Rollladen, richtung: str) -> None:
        r.s["letzte_" + richtung] = iso(self.u.jetzt())

    def fahrmodus(self, r: Rollladen, richtung: str) -> str:
        wert = r.s.get("fahrmodus_" + richtung)
        return wert if wert in FAHRMODI else FM_HELLIGKEIT

    def anwesenheit(self, r: Rollladen, richtung: str) -> str:
        wert = r.s.get("anwesenheit_" + richtung)
        return wert if wert in ANWESENHEIT else AW_IMMER

    def modus_erlaubt(self, r: Rollladen, richtung: str) -> bool:
        modus = self.anwesenheit(r, richtung)
        if modus == AW_AUS:
            return False
        if modus == AW_ABWESEND and self.u.jemand_da():
            return False
        return True

    def gesperrt(self, r: Rollladen) -> bool:
        bis = aus_iso(r.s["sperre_bis"])
        return bis is not None and self.u.jetzt() < bis

    def sperre_bis(self, r: Rollladen) -> datetime | None:
        return aus_iso(r.s["sperre_bis"]) if self.gesperrt(r) else None

    def frost_greift(self, r: Rollladen) -> bool:
        return (r.frostschutz and self.u.frost_aktiv()
                and r.s.get("frost_frei") != self.u.jetzt().date().isoformat())

    # ---- Zielzeiten ---------------------------------------------------

    def _fenster(self, r: Rollladen, richtung: str) -> tuple[time, time]:
        if richtung == HOCH:
            return r.zeit("hoch_frueh"), r.zeit("hoch_spaet")
        return r.zeit("runter_frueh"), r.zeit("runter_spaet")

    def zielzeit(self, r: Rollladen, richtung: str, tag: date,
                 modus: str | None = None) -> datetime:
        """Geplanter Fahrzeitpunkt (Anzeige, Phase nach Uhrzeit)."""
        frueh, spaet = self._fenster(r, richtung)
        modus = modus or self.fahrmodus(r, richtung)
        if modus == FM_ZEIT:
            return self._kombi(tag, frueh)
        if modus == FM_HELLIGKEIT:
            return self._kombi(tag, spaet)        # garantierte Fahrt
        adt = self.u.astro(richtung, tag)
        if adt is None:
            return self._kombi(tag, frueh if richtung == HOCH else spaet)
        return min(max(adt, self._kombi(tag, frueh)), self._kombi(tag, spaet))

    def fruehest(self, r: Rollladen, richtung: str, tag: date) -> datetime:
        """Frühestmöglicher Fahrzeitpunkt (Blocking-Zeiten)."""
        frueh, spaet = self._fenster(r, richtung)
        if self.fahrmodus(r, richtung) in (FM_ZEIT, FM_HELLIGKEIT):
            return self._kombi(tag, frueh)
        adt = self.u.astro(richtung, tag)
        if adt is None:
            return self._kombi(tag, frueh)
        return min(max(adt, self._kombi(tag, frueh)), self._kombi(tag, spaet))

    def naechste(self, r: Rollladen, richtung: str) -> datetime:
        heute = self.u.jetzt().date()
        tag = heute + timedelta(days=1) if self.gefahren_heute(r, richtung) else heute
        return self.zielzeit(r, richtung, tag)

    def _minuten_bis(self, r: Rollladen, richtung: str) -> float:
        heute = self.u.jetzt().date()
        tag = heute + timedelta(days=1) if self.gefahren_heute(r, richtung) else heute
        return (self.fruehest(r, richtung, tag) - self.u.jetzt()).total_seconds() / 60

    # ---- Phase und Griff ----------------------------------------------

    def phase(self, r: Rollladen) -> str:
        if self.gefahren_heute(r, RUNTER):
            return ZU
        if self.gefahren_heute(r, HOCH):
            return AUF
        jetzt = self.u.jetzt()
        auf_ab = self.zielzeit(r, HOCH, jetzt.date())
        zu_ab = self.zielzeit(r, RUNTER, jetzt.date())
        return AUF if auf_ab <= jetzt < zu_ab else ZU

    def griff_pos(self, r: Rollladen) -> int:
        """Position für den aktuellen Griffzustand (Zu-Phase)."""
        if not r.griff:
            return ZU_POS
        st = self.u.griff(r)
        if st == GRIFF_GEKIPPT:
            return r.gekippt_pos
        if st == GRIFF_OFFEN:
            return r.griff_offen_pos
        return ZU_POS          # zu / unbekannt -> zu

    def soll(self, r: Rollladen) -> int:
        """Gewünschte Position (Anzeige)."""
        if self.phase(r) == AUF:
            return self.g.beschattung_pos if r.beschattet else OFFEN_POS
        return self.griff_pos(r)

    def tuer_offen(self, r: Rollladen) -> bool:
        """Tür offen oder Griff unbekannt (im Zweifel nicht zufahren)."""
        if not r.tuer or not r.griff:
            return False
        return self.u.griff(r) not in (GRIFF_ZU, GRIFF_GEKIPPT)

    # ---- Bewegung -----------------------------------------------------

    def bewege(self, r: Rollladen, pos: int, grund: str, *,
               sicherheit: bool = False) -> bool:
        """Einzige Stelle, über die die Automatik fährt."""
        pos = int(pos)
        cur = self.u.position(r)

        # SICHERHEIT: bei offener Tür niemals zufahren (Aussperrschutz).
        if pos < OFFEN_POS and self.tuer_offen(r):
            r.s["grund"] = f"blockiert: Tür offen ({grund})"
            self.u.log(r, r.s["grund"])
            return False

        # Frostschutz: höchstens bis zur Frostposition öffnen.
        if not sicherheit and self.frost_greift(r):
            grenze = max(cur if cur is not None else ZU_POS, self.g.frost_pos)
            if pos > grenze:
                pos = grenze
                grund = f"{grund}, Frostschutz {self.g.frost_pos} %"
                self.u.frost_begrenzt(r)

        if cur is not None:
            r.s["letzte_pos"] = cur
        r.s["grund"] = grund
        r.s["soll_pos"] = pos
        r.s["soll_zeit"] = iso(self.u.jetzt())
        if cur is not None and cur == pos:
            return False
        self.u.fahre(r, pos)
        self.u.log(r, f"fahre → {pos} % | {grund}")
        return True

    def _tagesfahrt(self, r: Rollladen, pos: int, richtung: str,
                    grund: str) -> None:
        # Eine Automatik-Fahrt beendet eine laufende Handsperre.
        r.s["sperre_bis"] = None
        self.bewege(r, pos, grund)
        self._stempel(r, richtung)   # auch wenn schon in Position

    def _blocking(self, r: Rollladen, ziel: int, was: str) -> bool:
        """True, wenn die Fahrt wegen einer Blocking-Zeit unterbleibt."""
        cur = self.u.position(r)
        if cur is None:
            return False
        if ziel < cur and r.block_morgen > 0:
            rest = self._minuten_bis(r, HOCH)
            if 0 <= rest <= r.block_morgen:
                self.u.log(r, f"{was} unterdrückt – Morgenfahrt in {rest:.0f} min")
                return True
        elif ziel > cur and r.block_abend > 0:
            rest = self._minuten_bis(r, RUNTER)
            if 0 <= rest <= r.block_abend:
                self.u.log(r, f"{was} unterdrückt – Abendfahrt in {rest:.0f} min")
                return True
        return False

    def blocking_anzeige(self, r: Rollladen) -> str:
        aktiv = []
        if r.block_morgen > 0 and 0 <= self._minuten_bis(r, HOCH) <= r.block_morgen:
            aktiv.append("kein Zufahren")
        if r.block_abend > 0 and 0 <= self._minuten_bis(r, RUNTER) <= r.block_abend:
            aktiv.append("kein Auffahren")
        return " + ".join(aktiv) if aktiv else "–"

    # ---- Tagesfahrten -------------------------------------------------

    def bewerte(self, r: Rollladen) -> None:
        if not self.aktiv(r):
            return
        # Morgenfahrt läuft immer (auch bei Handsperre).
        if not self.gefahren_heute(r, HOCH) and self.modus_erlaubt(r, HOCH):
            self._vielleicht_fahren(r, HOCH)
        # Abendfahrt nur ohne aktive Sperre.
        if (not self.gefahren_heute(r, RUNTER) and not self.gesperrt(r)
                and self.modus_erlaubt(r, RUNTER)):
            self._vielleicht_fahren(r, RUNTER)

    def _vielleicht_fahren(self, r: Rollladen, richtung: str) -> None:
        jetzt = self.u.jetzt()
        frueh, spaet = self._fenster(r, richtung)
        modus = self.fahrmodus(r, richtung)
        lux = self.u.lux()
        if richtung == HOCH:
            if not frueh <= jetzt.time() < r.zeit("runter_frueh"):
                return
            pos = OFFEN_POS
            in_beschattung = self.beschattung_faellig(r)
            if in_beschattung:
                pos = self.g.beschattung_pos
        else:
            if jetzt.time() < frueh:
                return
            pos = self.griff_pos(r)
            in_beschattung = False

        ersatz = modus == FM_HELLIGKEIT and lux is None
        if ersatz:
            modus = FM_ASTRO
        zusatz = " → Beschattung" if in_beschattung else ""

        if modus == FM_HELLIGKEIT:
            assert lux is not None
            ok = (lux >= self.u.lux_hoch()) if richtung == HOCH \
                else (lux <= self.u.lux_runter())
            if ok:
                grund = f"Helligkeit {lux:.0f} lx"
            elif jetzt >= self._kombi(jetzt.date(), spaet):
                grund = "Zwangsfahrt (Spätzeit)"
            else:
                return
        else:
            # Modus explizit übergeben: beim Lux-Ersatz ist er Astro, nicht der
            # eingestellte (ASC rechnete hier mit Helligkeit = Spätzeit).
            if jetzt < self.zielzeit(r, richtung, jetzt.date(), modus):
                return
            grund = "Zeit" if modus == FM_ZEIT else (
                "Astro (Lux-Ersatz)" if ersatz else "Astro")
        self._tagesfahrt(r, pos, richtung, grund + zusatz)
        if in_beschattung:
            r.s["beschattet"] = True
            r.s["beschattung_zuletzt"] = iso(jetzt)

    # ---- Griff --------------------------------------------------------

    def griff_geaendert(self, r: Rollladen) -> None:
        """Nur in der Zu-Phase, unabhängig von Anwesenheit und Handsperre.
        Setzt keine Tages-Merker."""
        if not self.aktiv(r):
            return
        st = self.u.griff(r)
        # SICHERHEIT: Tür geöffnet -> immer ganz auf, Vorrang vor allem.
        if r.tuer and st == GRIFF_OFFEN:
            r.s["sperre_bis"] = None
            self.bewege(r, OFFEN_POS, "Tür offen → 100 % (Sicherheit)",
                        sicherheit=True)
            return
        if self.phase(r) != ZU:
            return
        ziel = self.griff_pos(r)
        if self._blocking(r, ziel, "Griff-Reaktion"):
            return
        self.bewege(r, ziel, f"Griff {st} → {ziel} %")

    # ---- Handbetrieb --------------------------------------------------

    def taster_gedrueckt(self, r: Rollladen) -> None:
        """Der Taster ist sicher eine Handfahrt: Referenz verwerfen, damit
        die folgende Positionsänderung als Handbetrieb erkannt wird."""
        r.s["soll_pos"] = None
        r.s["soll_zeit"] = None

    def position_geaendert(self, r: Rollladen, neu: Any, alt: Any) -> None:
        """Erkennt Handbetrieb: Position passt nicht zum eigenen Befehl."""
        if not self.aktiv(r):
            return
        pos = als_int(neu)
        if pos is None:
            return
        jetzt = self.u.jetzt()
        t_cmd = aus_iso(r.s["soll_zeit"])
        if t_cmd is not None and (jetzt - t_cmd).total_seconds() < MANUAL_SETTLE_S:
            return
        if r.s["soll_pos"] == pos:
            return

        # Jede Handfahrt gibt den Frostschutz bis zum Tagesende frei.
        r.s["frost_frei"] = jetzt.date().isoformat()

        alt_i = als_int(alt)
        heute = jetzt.date()
        jetzt_t = jetzt.time()
        tb = self._kombi(heute, r.zeit("hoch_frueh")) - timedelta(minutes=PHASE_VORLAUF_MIN)
        tagesbeginn = tb.time() if tb.date() == heute else time(0, 0)
        runter_frueh = r.zeit("runter_frueh")
        setze_auf = (alt_i is not None and pos > alt_i and pos >= OFFEN_POS
                     and tagesbeginn <= jetzt_t < runter_frueh
                     and not self.gefahren_heute(r, HOCH))
        setze_zu = (alt_i is not None and pos < alt_i
                    and jetzt_t >= runter_frueh
                    and not self.gefahren_heute(r, RUNTER))

        if setze_auf:
            self._stempel(r, HOCH)
            r.s["beschattet"] = False
            r.s["soll_pos"] = pos
            r.s["grund"] = f"Handbetrieb {pos} % – Auf-Phase gesetzt"
            self.u.log(r, r.s["grund"])
            return

        if self.phase(r) != ZU and not setze_zu and not r.beschattet:
            r.s["grund"] = f"Handbetrieb {pos} % (Auf-Phase, bleibt)"
            r.s["soll_pos"] = pos
            self.u.log(r, r.s["grund"])
            return

        if setze_zu:
            self._stempel(r, RUNTER)
        r.s["beschattet"] = False
        r.s["sperre_bis"] = iso(jetzt + timedelta(minutes=r.sperre_min))
        r.s["soll_pos"] = pos
        r.s["grund"] = f"Handbetrieb {pos} % – Sperre {r.sperre_min} min"
        self.u.log(r, r.s["grund"])

    def sperre_pruefen(self, r: Rollladen) -> None:
        """Nach Ablauf der Sperre auf die gewollte Position zurückfahren."""
        bis = aus_iso(r.s["sperre_bis"])
        if bis is None or self.u.jetzt() < bis:
            return
        r.s["sperre_bis"] = None
        if not self.aktiv(r) or self.phase(r) != ZU:
            return
        ziel = self.griff_pos(r)
        if self._blocking(r, ziel, "Sperren-Rückfahrt"):
            return
        self.bewege(r, ziel, f"Sperre abgelaufen → {ziel} %")

    # ---- Beschattung --------------------------------------------------

    def _anwesenheit_beschattung(self, modus: str) -> bool:
        if modus == BS_IMMER:
            return True
        if modus == BS_ANWESEND:
            return self.u.jemand_da()
        if modus == BS_ABWESEND:
            return not self.u.jemand_da()
        return False

    def beschattung_hindernis(self, r: Rollladen, *, phase: bool = True,
                              lux: bool = False) -> str | None:
        """Erster Grund, warum nicht beschattet wird; None = alles erfüllt."""
        if not r.beschattbar:
            return "kein Azimut"
        if not self.u.beschattung_an():
            return "Beschattung aus"
        if not self.u.automatik():
            return "Automatik Anlage aus"
        if not r.automatik:
            return "Automatik aus"
        modus = r.s.get("beschattung")
        if modus not in BESCHATTUNG or modus == BS_AUS:
            return "Modus aus"
        if not self._anwesenheit_beschattung(modus):
            return "Anwesenheit"
        if phase and self.phase(r) != AUF:
            return "Phase zu"
        if self.gesperrt(r):
            return "Handsperre"
        if r.griff and self.u.griff(r) in (GRIFF_GEKIPPT, GRIFF_OFFEN):
            return "Fenster offen"
        sonne = self.u.sonne()
        if sonne is None:
            return "Sonne ?"
        elevation, azimut = sonne
        if elevation < self.g.min_elevation:
            return f"Elevation {elevation:.0f}°"
        assert r.azimut_von is not None and r.azimut_bis is not None
        if not r.azimut_von <= azimut <= r.azimut_bis:
            return "Azimut raus"
        temp = self.u.temperatur()
        if temp is None or temp < self.g.min_temp:
            return "zu kalt"
        if lux:
            wert = self.u.lux()
            if wert is None or wert < self.g.sonnig:
                return "zu dunkel"
        return None

    def beschattung_faellig(self, r: Rollladen) -> bool:
        """Würde jetzt beschattet? Für die Morgenfahrt: ohne Phasenprüfung,
        weil der Hoch-Merker dann noch nicht gesetzt ist."""
        return self.beschattung_hindernis(r, phase=False, lux=True) is None

    def beschattung_grund(self, r: Rollladen) -> str:
        if r.beschattet:
            return "beschattet"
        return self.beschattung_hindernis(r, lux=True) or "bereit"

    def beschattung_pruefen(self, r: Rollladen) -> None:
        """Beschattung ein/aus mit Helligkeits-Hysterese und Wartezeit."""
        if not r.beschattbar:
            return
        jetzt = self.u.jetzt()
        aktiv = r.beschattet
        basis = self.beschattung_hindernis(r) is None
        lux = self.u.lux()

        # Grundbedingung weg: sofort, ohne Wartezeit.
        if aktiv and not basis:
            r.s["beschattet"] = False
            r.s["beschattung_zuletzt"] = iso(jetzt)
            if self.phase(r) == AUF and not self.gesperrt(r):
                self.bewege(r, OFFEN_POS, "Beschattung aus")
            else:
                r.s["grund"] = "Beschattung beendet"
            return

        if not aktiv:
            ziel = basis and lux is not None and lux >= self.g.sonnig
        else:
            # Ohne Messwert entschatten, sonst hängt er bis zum Abend fest.
            ziel = lux is not None and lux >= self.g.bewoelkt
        if ziel == aktiv:
            return
        zuletzt = aus_iso(r.s["beschattung_zuletzt"])
        if zuletzt is not None and (jetzt - zuletzt).total_seconds() < self.g.wartezeit_s:
            return
        r.s["beschattung_zuletzt"] = iso(jetzt)
        r.s["beschattet"] = ziel
        if ziel:
            self.bewege(r, self.g.beschattung_pos, f"Beschattung an ({lux:.0f} lx)")
        else:
            self.bewege(r, OFFEN_POS, "Beschattung aus (bewölkt)"
                        if lux is not None else "Beschattung aus (kein Lux-Wert)")


# ----------------------------------------------------------------------
#  Frost
# ----------------------------------------------------------------------

NASS_WETTER = {"rainy", "pouring", "snowy", "snowy-rainy", "hail", "lightning-rainy"}


def frost_bewerten(f: dict[str, Any], jetzt: datetime, *,
                   temp: float | None,
                   schwelle: float, hysterese: float, stunden: float,
                   niederschlag_quelle: bool, niederschlag: float | None,
                   feuchte_quelle: bool, feuchte: float | None,
                   feuchte_schwelle: float,
                   wetter_quelle: bool, wetter: str | None) -> None:
    """Aktualisiert den Frostzustand ``f`` (gespeichert) in place.

    Schlüssel: kalt, nass, letzter_niederschlag, letzte_feuchte, grund.
    Kalt mit Hysterese; ohne Temperatur bleibt der letzte Zustand.
    Nass, wenn in den letzten ``stunden`` Niederschlag fiel oder es über
    0 °C feucht war (Luftfeuchte >= Schwelle). Ohne jede Nässequelle gilt
    immer nass; fällt der Niederschlagssensor aus, ebenfalls.
    """
    kalt = bool(f.get("kalt", False))
    if temp is not None:
        if not kalt and temp < schwelle:
            kalt = True
        elif kalt and temp > schwelle + hysterese:
            kalt = False
    f["kalt"] = kalt

    if niederschlag_quelle and niederschlag is not None and niederschlag > 0:
        f["letzter_niederschlag"] = iso(jetzt)
    if wetter_quelle and wetter in NASS_WETTER:
        f["letzter_niederschlag"] = iso(jetzt)
    if (feuchte_quelle and feuchte is not None and temp is not None
            and temp > 0 and feuchte >= feuchte_schwelle):
        f["letzte_feuchte"] = iso(jetzt)

    grenze = jetzt - timedelta(hours=stunden)
    gruende = []
    if not (niederschlag_quelle or feuchte_quelle or wetter_quelle):
        gruende.append("keine Nässequelle")
    if niederschlag_quelle and niederschlag is None:
        gruende.append("Niederschlag unbekannt")
    regen = aus_iso(f.get("letzter_niederschlag"))
    if regen is not None and regen >= grenze:
        gruende.append("Niederschlag")
    feucht = aus_iso(f.get("letzte_feuchte"))
    if feucht is not None and feucht >= grenze:
        gruende.append("feucht über 0 °C")
    f["nass"] = bool(gruende)
    if not kalt:
        f["grund"] = "nicht kalt" if temp is not None else "Temperatur unbekannt"
    elif not gruende:
        f["grund"] = "trocken"
    else:
        f["grund"] = "kalt, " + ", ".join(gruende)
