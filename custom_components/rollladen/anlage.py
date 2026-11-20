"""Anlage: verbindet die Logik mit Home Assistant.

Liest Zustände, hört auf Änderungen, fährt die Cover und hält den
Speicher. Die Entscheidungen trifft ``logik.Rechner``.

Gespeichert (Store, übersteht Neustarts): Anlagenwerte (Automatik,
Beschattung, Frostschutz, Lux-Schwellen, Frostschwelle), der Frostzustand
und je Rollladen Einstellungen und Zustand (Tages-Merker, Handsperre,
Beschattung, eigene Sollposition, Frostfreigabe).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .const import (
    ANLAGE_DEFAULTS,
    ANLAGE_SPEICHER_DEFAULTS,
    CONF_ANWESENHEIT,
    CONF_AZIMUT_BIS,
    CONF_AZIMUT_VON,
    CONF_BESCHATTUNG_POS,
    CONF_BEWOELKT,
    CONF_BLOCK_ABEND,
    CONF_BLOCK_MORGEN,
    CONF_COVER,
    CONF_FEUCHTE,
    CONF_FEUCHTE_SCHWELLE,
    CONF_FROST_HYSTERESE,
    CONF_FROST_POS,
    CONF_FROST_STUNDEN,
    CONF_FROSTSCHUTZ,
    CONF_GEKIPPT_POS,
    CONF_GRIFF,
    CONF_GRIFF_OFFEN_POS,
    CONF_LUX_MITTEL,
    CONF_LUX_SENSOR,
    CONF_MIN_ELEVATION,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_NIEDERSCHLAG,
    CONF_NOTIFY,
    CONF_ROLLLAEDEN,
    CONF_SONNIG,
    CONF_SPERRE_MIN,
    CONF_TASTER,
    CONF_TASTER_KURZ,
    CONF_TASTER_LANG,
    CONF_TEMPERATUR,
    CONF_TUER,
    CONF_WARTEZEIT,
    CONF_WETTER,
    DOMAIN,
    ENTITY_KEYS_ANLAGE,
    ENTITY_KEYS_ROLLLADEN,
    FAHR_ABSTAND,
    LUX_AUSFALL_SEKUNDEN,
    ROLLLADEN_DEFAULTS,
    START_VERZOEGERUNG,
    ZYKLUS_SEKUNDEN,
)
from .logik import (
    HOCH,
    Global,
    Rechner,
    Rollladen,
    entity_ersetzen,
    entity_verweise,
    frost_bewerten,
    griff_wechsel,
    griff_wert,
    jemand_da as logik_jemand_da,
    lang_wiederholung,
    lux_mittel,
    lux_proben_kuerzen,
    protokoll_neu,
    taster_aktion,
)

_LOGGER = logging.getLogger(__name__)

SPEICHER_VERSION = 1
UNGUELTIG = (None, STATE_UNAVAILABLE, STATE_UNKNOWN, "")
DIENST_TIMEOUT = 15
ISSUE_FEHLEND = "fehlende_entities"


def _liste(wert: Any) -> list[str]:
    """Ein oder mehrere Entity-IDs als Liste."""
    if not wert:
        return []
    if isinstance(wert, str):
        return [wert]
    return [str(w) for w in wert if w]


def _zahl_oder_none(wert: Any) -> float | None:
    if wert in (None, ""):
        return None
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


class Anlage:
    """Alle Rollläden einer Installation (ein Config-Eintrag)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(
            hass, SPEICHER_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.daten: dict[str, Any] = {}
        self.rolllaeden: dict[str, Rollladen] = {}
        self.geraet_id: str | None = None
        self.gestartet = False

        self._listener: list[CALLBACK_TYPE] = []
        self._abmelden: list[CALLBACK_TYPE] = []
        # Frostschutz: Rollläden, die in diesem Durchlauf begrenzt wurden.
        self._frost_neu: list[str] = []
        # Zuordnung Entity -> Rollläden für die Listener.
        self._covers: dict[str, Rollladen] = {}
        self._griffe: dict[str, list[Rollladen]] = {}
        self._taster: dict[str, list[Rollladen]] = {}
        # Fahrabstand: frühester Start der nächsten Automatik-Fahrt.
        self._frei_ab = 0.0
        self._wartend: list[CALLBACK_TYPE] = []
        # Helligkeit: (Zeitstempel, Wert) für den gleitenden Mittelwert.
        self._lux_proben: list[tuple[float, float]] = []
        # Letzter langer Tastendruck je Rollladen (Wiederholungen beim Halten).
        self._lang_zuletzt: dict[str, float] = {}

        self.rechner = Rechner(self, self._global())

    # ------------------------------------------------------------------
    #  Lebenszyklus
    # ------------------------------------------------------------------

    @property
    def opt(self) -> dict[str, Any]:
        return {**ANLAGE_DEFAULTS, **self.entry.options}

    @property
    def a(self) -> dict[str, Any]:
        return self.daten["anlage"]

    @property
    def frost(self) -> dict[str, Any]:
        return self.daten["frost"]

    def _global(self) -> Global:
        o = self.opt
        return Global(
            beschattung_pos=int(o[CONF_BESCHATTUNG_POS]),
            min_elevation=float(o[CONF_MIN_ELEVATION]),
            min_temp=float(o[CONF_MIN_TEMP]),
            sonnig=float(o[CONF_SONNIG]),
            bewoelkt=float(o[CONF_BEWOELKT]),
            wartezeit_s=float(o[CONF_WARTEZEIT]) * 60,
            frost_pos=int(o[CONF_FROST_POS]),
        )

    def sortiert(self) -> list[Rollladen]:
        return sorted(self.rolllaeden.values(), key=lambda r: r.name.lower())

    async def async_laden(self) -> None:
        self.daten = await self.store.async_load() or {}
        anlage = self.daten.setdefault("anlage", {})
        for key, wert in ANLAGE_SPEICHER_DEFAULTS.items():
            anlage.setdefault(key, wert)
        self.daten.setdefault("frost", {})
        self.daten.setdefault("frost_gemeldet", {})
        speicher = self.daten.setdefault("rolllaeden", {})
        for rid, d in self.entry.options.get(CONF_ROLLLAEDEN, {}).items():
            k = {**ROLLLADEN_DEFAULTS, **d}
            self.rolllaeden[rid] = Rollladen(
                rid, str(k[CONF_NAME]), str(k[CONF_COVER]),
                speicher.setdefault(rid, {}),
                taster=_liste(k.get(CONF_TASTER)),
                taster_kurz=str(k[CONF_TASTER_KURZ]),
                taster_lang=str(k[CONF_TASTER_LANG]),
                griff=k.get(CONF_GRIFF) or None,
                tuer=bool(k[CONF_TUER]),
                gekippt_pos=int(k[CONF_GEKIPPT_POS]),
                griff_offen_pos=int(k[CONF_GRIFF_OFFEN_POS]),
                azimut_von=_zahl_oder_none(k.get(CONF_AZIMUT_VON)),
                azimut_bis=_zahl_oder_none(k.get(CONF_AZIMUT_BIS)),
                sperre_min=int(k[CONF_SPERRE_MIN]),
                block_morgen=int(k[CONF_BLOCK_MORGEN]),
                block_abend=int(k[CONF_BLOCK_ABEND]),
                frostschutz=bool(k[CONF_FROSTSCHUTZ]),
            )
        for rid in list(speicher):
            if rid not in self.rolllaeden:
                del speicher[rid]
        self.speichern()

    @callback
    def async_start(self) -> None:
        o = self.opt
        global_ids = [e for e in (o.get(CONF_LUX_SENSOR), o.get(CONF_TEMPERATUR),
                                  o.get(CONF_NIEDERSCHLAG), o.get(CONF_FEUCHTE),
                                  o.get(CONF_WETTER)) if e]
        global_ids += _liste(o.get(CONF_ANWESENHEIT))
        self._lux_probe()
        if global_ids:
            self._abmelden.append(async_track_state_change_event(
                self.hass, global_ids, self._on_global))
        covers = {r.cover: r for r in self.rolllaeden.values()}
        if covers:
            self._abmelden.append(async_track_state_change_event(
                self.hass, list(covers), self._on_cover))
        griffe: dict[str, list[Rollladen]] = {}
        taster: dict[str, list[Rollladen]] = {}
        for r in self.rolllaeden.values():
            if r.griff:
                griffe.setdefault(r.griff, []).append(r)
            for t in r.taster:
                taster.setdefault(t, []).append(r)
        self._griffe = griffe
        self._taster = taster
        self._covers = covers
        if griffe:
            self._abmelden.append(async_track_state_change_event(
                self.hass, list(griffe), self._on_griff))
            for r in self.rolllaeden.values():
                roh = self._zustand(r.griff)
                if r.griff and roh not in UNGUELTIG:
                    r.s["griff_zuletzt"] = roh
        if taster:
            self._abmelden.append(async_track_state_change_event(
                self.hass, list(taster), self._on_taster))
        self._abmelden.append(self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry))
        self._abmelden.append(async_at_started(self.hass, self._on_ha_gestartet))

    async def async_stop(self) -> None:
        self.gestartet = False
        for abmelden in self._abmelden + self._wartend:
            abmelden()
        self._abmelden.clear()
        self._wartend.clear()
        await self.store.async_save(self.daten)

    async def _on_ha_gestartet(self, _hass: HomeAssistant) -> None:
        # Erste Auswertung etwas später, damit Cover und Sensoren da sind.
        self._abmelden.append(async_call_later(
            self.hass, START_VERZOEGERUNG, self._erster_zyklus))

    async def _erster_zyklus(self, _now: datetime) -> None:
        self.gestartet = True
        self._abmelden.append(async_track_time_interval(
            self.hass, self._takt, timedelta(seconds=ZYKLUS_SEKUNDEN)))
        _LOGGER.info("Rollladen gestartet (%d Rollläden)", len(self.rolllaeden))
        self.verweise_pruefen()
        self.bereiche_setzen()
        self.zyklus()

    @callback
    def _takt(self, _now: datetime) -> None:
        self.zyklus(sperren=True)

    def speichern(self) -> None:
        self.store.async_delay_save(lambda: self.daten, 2)

    @callback
    def async_add_listener(self, cb: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listener.append(cb)
        return lambda: self._listener.remove(cb)

    @callback
    def benachrichtigen(self) -> None:
        for cb in list(self._listener):
            cb()

    # ------------------------------------------------------------------
    #  Auswertung
    # ------------------------------------------------------------------

    @callback
    def zyklus(self, *, sperren: bool = False,
               nur: Rollladen | None = None) -> None:
        """Alle (oder einen) Rollläden auswerten."""
        if not self.gestartet:
            return
        self._frost_aktualisieren()
        for r in [nur] if nur else self.sortiert():
            if sperren:
                self.rechner.sperre_pruefen(r)
            self.rechner.bewerte(r)
            self.rechner.beschattung_pruefen(r)
        self._abschluss()

    @callback
    def _abschluss(self) -> None:
        self._frost_melden()
        self.speichern()
        self.benachrichtigen()

    @callback
    def _on_global(self, event: Event[EventStateChangedData]) -> None:
        if event.data["entity_id"] == self.opt.get(CONF_LUX_SENSOR):
            self._lux_probe()
        self.zyklus()

    @callback
    def _lux_probe(self) -> None:
        """Aktuellen Helligkeitswert in die Proben übernehmen."""
        entity_id = self.opt.get(CONF_LUX_SENSOR)
        st = self.hass.states.get(entity_id) if entity_id else None
        wert = self._zahl(entity_id)
        if st is None or wert is None:
            return
        self._lux_proben.append((st.last_updated.timestamp(), wert))
        self._lux_proben = lux_proben_kuerzen(
            self._lux_proben, dt_util.utcnow().timestamp(), self._lux_fenster())

    def _lux_fenster(self) -> float:
        return float(self.opt[CONF_LUX_MITTEL]) * 60

    @callback
    def _on_cover(self, event: Event[EventStateChangedData]) -> None:
        r = self._covers.get(event.data["entity_id"])
        alt, neu = event.data["old_state"], event.data["new_state"]
        if r is None or not self.gestartet or neu is None:
            return
        pos_neu = neu.attributes.get("current_position")
        pos_alt = alt.attributes.get("current_position") if alt else None
        if pos_neu is not None and pos_neu != pos_alt:
            self.rechner.position_geaendert(r, pos_neu, pos_alt)
        self._abschluss()

    @callback
    def _on_griff(self, event: Event[EventStateChangedData]) -> None:
        neu = event.data["new_state"]
        roh = neu.state if neu else None
        for r in self._griffe.get(event.data["entity_id"], []):
            # unavailable/unknown (Neustart, Funk) ist kein Griffwechsel.
            if not griff_wechsel(r.s.get("griff_zuletzt"), roh):
                continue
            # Merken auch vor dem Start, reagieren erst danach.
            r.s["griff_zuletzt"] = roh
            if self.gestartet:
                self.rechner.griff_geaendert(r)
                self.rechner.beschattung_pruefen(r)
        self._abschluss()

    @callback
    def _on_taster(self, event: Event[EventStateChangedData]) -> None:
        alt, neu = event.data["old_state"], event.data["new_state"]
        # Nur echte Tastendrücke: nicht beim Start (unavailable -> Zustand).
        if (neu is None or alt is None or alt.state in UNGUELTIG
                or neu.state in UNGUELTIG or alt.state == neu.state):
            return
        art = neu.attributes.get("event_type")
        for r in self._taster.get(event.data["entity_id"], []):
            if art == r.taster_lang:
                jetzt = self.hass.loop.time()
                wiederholt = lang_wiederholung(self._lang_zuletzt.get(r.id), jetzt)
                self._lang_zuletzt[r.id] = jetzt
                if not wiederholt:
                    self._taster_fahren(r, lang=True)
            elif art == r.taster_kurz:
                self._taster_fahren(r, lang=False)
        self._abschluss()

    @callback
    def _taster_fahren(self, r: Rollladen, *, lang: bool) -> None:
        st = self.hass.states.get(r.cover)
        status = st.state if st else None
        pos = st.attributes.get("current_position") if st else None
        aktion = taster_aktion(lang, status, pos)
        self.rechner.taster_gedrueckt(r)
        self._protokoll(r, f"Taster {'lang' if lang else 'kurz'} → {aktion}")
        dienst = {"auf": "open_cover", "zu": "close_cover",
                  "stopp": "stop_cover"}[aktion]
        _LOGGER.debug("[%s] Taster %s → %s", r.name,
                      "lang" if lang else "kurz", aktion)
        self.hass.async_create_task(self._dienst(
            "cover", dienst, {"entity_id": r.cover}))

    # ------------------------------------------------------------------
    #  Frostschutz
    # ------------------------------------------------------------------

    @callback
    def _frost_aktualisieren(self) -> None:
        o = self.opt
        frost_bewerten(
            self.frost, dt_util.now(),
            temp=self._zahl(o.get(CONF_TEMPERATUR)),
            schwelle=float(self.a["frost_schwelle"]),
            hysterese=float(o[CONF_FROST_HYSTERESE]),
            stunden=float(o[CONF_FROST_STUNDEN]),
            niederschlag_quelle=bool(o.get(CONF_NIEDERSCHLAG)),
            niederschlag=self._zahl(o.get(CONF_NIEDERSCHLAG)),
            feuchte_quelle=bool(o.get(CONF_FEUCHTE)),
            feuchte=self._zahl(o.get(CONF_FEUCHTE)),
            feuchte_schwelle=float(o[CONF_FEUCHTE_SCHWELLE]),
            wetter_quelle=bool(o.get(CONF_WETTER)),
            wetter=self._zustand(o.get(CONF_WETTER)),
        )

    @callback
    def _frost_melden(self) -> None:
        """Eine Push-Nachricht je Rollladen und Tag, gesammelt."""
        if not self._frost_neu:
            return
        heute = dt_util.now().date().isoformat()
        g = self.daten["frost_gemeldet"]
        if g.get("datum") != heute:
            g.clear()
            g["datum"] = heute
            g["namen"] = []
        neu = [n for n in self._frost_neu if n not in g["namen"]]
        self._frost_neu.clear()
        if not neu:
            return
        g["namen"] = [*g["namen"], *neu]
        text = (f"Frostschutz aktiv: {', '.join(neu)} nur auf "
                f"{self.rechner.g.frost_pos} % geöffnet. Ganz öffnen per "
                "Taster oder Dashboard.")
        _LOGGER.info("%s", text)
        self._push(text)

    def _push(self, text: str) -> None:
        roh = self.opt.get(CONF_NOTIFY) or []
        for dienst in [roh] if isinstance(roh, str) else roh:
            dienst = str(dienst).strip().replace("/", ".")
            if "." not in dienst:
                continue
            domain, service = dienst.split(".", 1)
            self.hass.async_create_task(self._dienst(
                domain, service, {"title": "Rollladen", "message": text}))

    # ------------------------------------------------------------------
    #  Bedienung über die Entities
    # ------------------------------------------------------------------

    @callback
    def setze_anlage(self, key: str, wert: Any) -> None:
        self.a[key] = wert
        if self.gestartet:
            self.zyklus()
        else:
            self._abschluss()

    @callback
    def setze_wert(self, r: Rollladen, key: str, wert: Any) -> None:
        r.s[key] = wert
        if self.gestartet:
            self.zyklus(nur=r)
        else:
            self._abschluss()

    # ------------------------------------------------------------------
    #  Umgebung für die Logik
    # ------------------------------------------------------------------

    def jetzt(self) -> datetime:
        return dt_util.now()

    def automatik(self) -> bool:
        return bool(self.a["automatik"])

    def beschattung_an(self) -> bool:
        return bool(self.a["beschattung"])

    def frost_aktiv(self) -> bool:
        return (bool(self.a["frostschutz"]) and bool(self.frost.get("kalt"))
                and bool(self.frost.get("nass")))

    def lux(self) -> float | None:
        """Gleitender Mittelwert der Helligkeit (Ausreißer zählen wenig).
        Kurze Ausfälle überbrückt der letzte Wert, lange gelten als „kein
        Wert“."""
        entity_id = self.opt.get(CONF_LUX_SENSOR)
        st = self.hass.states.get(entity_id) if entity_id else None
        if st is None:
            return None
        jetzt = dt_util.utcnow().timestamp()
        if (st.state in UNGUELTIG
                and jetzt - st.last_changed.timestamp() > LUX_AUSFALL_SEKUNDEN):
            return None
        return lux_mittel(self._lux_proben, jetzt, self._lux_fenster())

    def lux_hoch(self) -> float:
        return float(self.a["lux_hoch"])

    def lux_runter(self) -> float:
        return float(self.a["lux_runter"])

    def jemand_da(self) -> bool:
        """Mindestens eine Person zuhause. Unklar = zuhause (sicher)."""
        return logik_jemand_da([self._zustand(e) for e in
                                _liste(self.opt.get(CONF_ANWESENHEIT))])

    def temperatur(self) -> float | None:
        return self._zahl(self.opt.get(CONF_TEMPERATUR))

    def sonne(self) -> tuple[float, float] | None:
        st = self.hass.states.get("sun.sun")
        if st is None:
            return None
        try:
            return (float(st.attributes["elevation"]),
                    float(st.attributes["azimuth"]))
        except (KeyError, TypeError, ValueError):
            return None

    def astro(self, richtung: str, tag: date) -> datetime | None:
        ereignis = "sunrise" if richtung == HOCH else "sunset"
        wann = get_astral_event_date(self.hass, ereignis, tag)
        return dt_util.as_local(wann) if wann else None

    def griff(self, r: Rollladen) -> str | None:
        if not r.griff:
            return None
        return griff_wert(self._zustand(r.griff), r.s.get("griff_zuletzt"),
                          r.tuer)

    def position(self, r: Rollladen) -> int | None:
        st = self.hass.states.get(r.cover)
        if st is None or st.state in UNGUELTIG:
            return None
        wert = st.attributes.get("current_position")
        return int(wert) if wert is not None else None

    def fahre(self, r: Rollladen, pos: int) -> None:
        """Automatik-Fahrt, mit FAHR_ABSTAND zur vorherigen."""
        jetzt = self.hass.loop.time()
        warten = max(0.0, self._frei_ab - jetzt)
        self._frei_ab = jetzt + warten + FAHR_ABSTAND
        grund = r.grund
        zusatz = f" (+{warten:.1f} s)" if warten else ""
        self._protokoll(r, f"→ {pos} % | {grund}{zusatz}")
        if not warten:
            self._fahre_jetzt(r, pos)
            return

        @callback
        def _spaeter(_now: datetime) -> None:
            self._wartend.remove(abbrechen)
            self._fahre_jetzt(r, pos)

        abbrechen = async_call_later(self.hass, warten, _spaeter)
        self._wartend.append(abbrechen)

    @callback
    def _fahre_jetzt(self, r: Rollladen, pos: int) -> None:
        if self.hass.is_stopping:
            _LOGGER.info("[%s] Fahrt auf %s %% entfällt: HA fährt herunter",
                         r.name, pos)
            return
        self.hass.async_create_task(self._dienst(
            "cover", "set_cover_position",
            {"entity_id": r.cover, "position": pos}))

    def _protokoll(self, r: Rollladen, text: str) -> None:
        zeit = dt_util.now().strftime("%d.%m. %H:%M:%S")
        r.s["protokoll"] = protokoll_neu(r.s.get("protokoll"), f"{zeit} {text}")

    def frost_begrenzt(self, r: Rollladen) -> None:
        if r.name not in self._frost_neu:
            self._frost_neu.append(r.name)

    def log(self, r: Rollladen, text: str) -> None:
        _LOGGER.info("[%s] %s", r.name, text)

    # ------------------------------------------------------------------
    #  Verweise: Umbenennen folgen, Fehlende unter „Reparaturen“ melden
    # ------------------------------------------------------------------

    def _verweise(self) -> list[tuple[str | None, str, str]]:
        return entity_verweise(dict(self.entry.options), ENTITY_KEYS_ANLAGE,
                               ENTITY_KEYS_ROLLLADEN, CONF_ROLLLAEDEN)

    @callback
    def _on_registry(self, event: Event[er.EventEntityRegistryUpdatedData]
                     ) -> None:
        daten = event.data
        alt = daten.get("old_entity_id")
        if daten["action"] == "update" and alt:
            neu = entity_ersetzen(dict(self.entry.options), alt,
                                  daten["entity_id"], ENTITY_KEYS_ANLAGE,
                                  ENTITY_KEYS_ROLLLADEN, CONF_ROLLLAEDEN)
            if neu is not None:
                _LOGGER.info("Umbenannt: %s → %s, Einstellungen angepasst",
                             alt, daten["entity_id"])
                # Lädt die Anlage über den Update-Listener neu.
                self.hass.config_entries.async_update_entry(
                    self.entry, options=neu)
                return
        if self.gestartet and any(
                e == daten["entity_id"] for _, _, e in self._verweise()):
            self.verweise_pruefen()

    @callback
    def bereiche_setzen(self) -> None:
        """Neuen Rollladen-Geräten einmal den Bereich ihres Covers geben.

        Läuft erst, wenn die Entities angelegt sind, damit der Bereich nicht
        in die Entity-IDs gerät. Danach gehört der Bereich dir: Änderst oder
        löschst du ihn, bleibt das so."""
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        for r in self.rolllaeden.values():
            if r.s.get("bereich_gesetzt"):
                continue
            geraet = dev_reg.async_get_device(identifiers={(DOMAIN, r.id)})
            if geraet is None:
                continue
            r.s["bereich_gesetzt"] = True
            if geraet.area_id:
                continue
            cover = ent_reg.async_get(r.cover)
            area_id = cover.area_id if cover else None
            if area_id is None and cover and cover.device_id:
                cover_geraet = dev_reg.async_get(cover.device_id)
                area_id = cover_geraet.area_id if cover_geraet else None
            if area_id:
                dev_reg.async_update_device(geraet.id, area_id=area_id)
                _LOGGER.info("[%s] Bereich vom Cover übernommen", r.name)
        self.speichern()

    def _fehlt(self, entity_id: str) -> str | None:
        """Grund, warum eine Entity fehlt, sonst None."""
        eintrag = er.async_get(self.hass).async_get(entity_id)
        if eintrag is not None:
            return "deaktiviert" if eintrag.disabled_by else None
        return None if self.hass.states.get(entity_id) else "gibt es nicht"

    @callback
    def verweise_pruefen(self) -> None:
        """Fehlende oder deaktivierte Entities als Reparatur melden."""
        namen = {rid: r.name for rid, r in self.rolllaeden.items()}
        zeilen = []
        for rid, key, entity_id in self._verweise():
            grund = self._fehlt(entity_id)
            if grund:
                wo = namen.get(rid, rid) if rid else "Anlage"
                zeilen.append(f"- {wo}, {key}: `{entity_id}` ({grund})")
        issue_id = f"{ISSUE_FEHLEND}_{self.entry.entry_id}"
        if not zeilen:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        _LOGGER.warning("Fehlende Entities:\n%s", "\n".join(zeilen))
        ir.async_create_issue(
            self.hass, DOMAIN, issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_FEHLEND,
            translation_placeholders={"liste": "\n".join(zeilen)},
        )

    # ------------------------------------------------------------------
    #  Hilfen
    # ------------------------------------------------------------------

    def _zustand(self, entity_id: str | None) -> str | None:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    def _zahl(self, entity_id: str | None) -> float | None:
        roh = self._zustand(entity_id)
        if roh in UNGUELTIG:
            return None
        try:
            return float(roh)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            _LOGGER.warning("Unerwarteter Wert bei %s: %r", entity_id, roh)
            return None

    async def _dienst(self, domain: str, service: str,
                      daten: dict[str, Any]) -> bool:
        try:
            await asyncio.wait_for(self.hass.services.async_call(
                domain, service, daten, blocking=True), DIENST_TIMEOUT)
        except (HomeAssistantError, TimeoutError, ValueError) as err:
            _LOGGER.warning("Aufruf %s.%s fehlgeschlagen: %s",
                            domain, service, err)
            return False
        return True
