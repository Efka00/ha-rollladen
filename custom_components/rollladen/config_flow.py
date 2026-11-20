"""Config-Flow: Anlage anlegen; Optionen = Anlage, Frostschutz, Rollläden.

Die Rollläden liegen in den Optionen der Anlage unter CONF_ROLLLAEDEN als
{rollladen_id: {...}}.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.util import slugify
from homeassistant.util.ulid import ulid_now

from .const import (
    ANLAGE_DEFAULTS,
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
    ROLLLADEN_DEFAULTS,
)

CONF_AUSWAHL = "rollladen"

GANZZAHLEN = (CONF_BESCHATTUNG_POS, CONF_SONNIG, CONF_BEWOELKT, CONF_FROST_POS,
              CONF_FEUCHTE_SCHWELLE, CONF_GEKIPPT_POS, CONF_GRIFF_OFFEN_POS,
              CONF_SPERRE_MIN, CONF_BLOCK_MORGEN, CONF_BLOCK_ABEND,
              CONF_WARTEZEIT)


def _zahl(minimum: float, maximum: float, schritt: float = 1,
          einheit: str | None = None) -> selector.NumberSelector:
    konfig = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=schritt,
        mode=selector.NumberSelectorMode.BOX,
    )
    # unit_of_measurement=None ist ungültig (HTTP 400), nur mit Einheit setzen.
    if einheit:
        konfig["unit_of_measurement"] = einheit
    return selector.NumberSelector(konfig)


def _optional(key: str, werte: dict[str, Any]) -> vol.Optional:
    """Optionales Feld, das einen vorhandenen Wert vorbelegt."""
    if werte.get(key) not in (None, ""):
        return vol.Optional(key, description={"suggested_value": werte[key]})
    return vol.Optional(key)


def _entity(domain: str | list[str], **kwargs: Any) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=domain, **kwargs))


def notify_liste(wert: Any) -> list[str]:
    if not wert:
        return []
    if isinstance(wert, str):
        return [wert]
    return [str(w) for w in wert if w]


def _handys(hass: HomeAssistant, aktuell: Any) -> selector.SelectSelector:
    """Mehrfachauswahl der Handys aus der Companion-App (notify.mobile_app_*).

    Gespeicherte Dienste bleiben wählbar, auch wenn sie gerade nicht
    registriert sind.
    """
    optionen: list[selector.SelectOptionDict] = []
    for eintrag in hass.config_entries.async_entries("mobile_app"):
        name = str(eintrag.data.get("device_name") or eintrag.title)
        dienst = f"mobile_app_{slugify(name)}"
        if hass.services.has_service("notify", dienst):
            optionen.append(selector.SelectOptionDict(
                value=f"notify.{dienst}", label=name))
    optionen.sort(key=lambda o: o["label"].lower())
    vorhanden = {o["value"] for o in optionen}
    for dienst in notify_liste(aktuell):
        if dienst not in vorhanden:
            optionen.append(selector.SelectOptionDict(value=dienst, label=dienst))
    return selector.SelectSelector(selector.SelectSelectorConfig(
        options=optionen, multiple=True,
        mode=selector.SelectSelectorMode.DROPDOWN))


def _anlage_schema(hass: HomeAssistant, werte: dict[str, Any]) -> vol.Schema:
    w = {**ANLAGE_DEFAULTS, **werte}
    return vol.Schema({
        vol.Required(CONF_LUX_SENSOR,
                     description={"suggested_value": w.get(CONF_LUX_SENSOR)}):
            _entity("sensor", device_class="illuminance"),
        _optional(CONF_ANWESENHEIT, w):
            _entity(["binary_sensor", "person", "group", "input_boolean"]),
        _optional(CONF_TEMPERATUR, w): _entity("sensor", device_class="temperature"),
        vol.Required(CONF_BESCHATTUNG_POS, default=w[CONF_BESCHATTUNG_POS]):
            _zahl(0, 100, 1, "%"),
        vol.Required(CONF_MIN_ELEVATION, default=w[CONF_MIN_ELEVATION]):
            _zahl(0, 90, 1, "°"),
        vol.Required(CONF_MIN_TEMP, default=w[CONF_MIN_TEMP]):
            _zahl(-10, 40, 0.5, "°C"),
        vol.Required(CONF_SONNIG, default=w[CONF_SONNIG]):
            _zahl(0, 200000, 500, "lx"),
        vol.Required(CONF_BEWOELKT, default=w[CONF_BEWOELKT]):
            _zahl(0, 200000, 500, "lx"),
        vol.Required(CONF_WARTEZEIT, default=w[CONF_WARTEZEIT]):
            _zahl(0, 120, 1, "min"),
        vol.Optional(CONF_NOTIFY, default=notify_liste(w.get(CONF_NOTIFY))):
            _handys(hass, w.get(CONF_NOTIFY)),
    })


def _frost_schema(werte: dict[str, Any]) -> vol.Schema:
    w = {**ANLAGE_DEFAULTS, **werte}
    return vol.Schema({
        vol.Required(CONF_FROST_POS, default=w[CONF_FROST_POS]):
            _zahl(0, 100, 1, "%"),
        vol.Required(CONF_FROST_HYSTERESE, default=w[CONF_FROST_HYSTERESE]):
            _zahl(0, 5, 0.5, "K"),
        vol.Required(CONF_FROST_STUNDEN, default=w[CONF_FROST_STUNDEN]):
            _zahl(1, 168, 1, "h"),
        _optional(CONF_NIEDERSCHLAG, w): _entity("sensor"),
        _optional(CONF_FEUCHTE, w): _entity("sensor", device_class="humidity"),
        vol.Required(CONF_FEUCHTE_SCHWELLE, default=w[CONF_FEUCHTE_SCHWELLE]):
            _zahl(50, 100, 1, "%"),
        _optional(CONF_WETTER, w): _entity("weather"),
    })


def _rollladen_schema(werte: dict[str, Any]) -> vol.Schema:
    w = {**ROLLLADEN_DEFAULTS, **werte}
    return vol.Schema({
        vol.Required(CONF_NAME, default=w.get(CONF_NAME, "")):
            selector.TextSelector(),
        vol.Required(CONF_COVER,
                     description={"suggested_value": w.get(CONF_COVER)}):
            _entity("cover"),
        _optional(CONF_TASTER, w): _entity("event", multiple=True),
        vol.Required(CONF_TASTER_KURZ, default=w[CONF_TASTER_KURZ]):
            selector.TextSelector(),
        vol.Required(CONF_TASTER_LANG, default=w[CONF_TASTER_LANG]):
            selector.TextSelector(),
        _optional(CONF_GRIFF, w): _entity("sensor"),
        vol.Required(CONF_TUER, default=w[CONF_TUER]): selector.BooleanSelector(),
        vol.Required(CONF_GEKIPPT_POS, default=w[CONF_GEKIPPT_POS]):
            _zahl(0, 100, 1, "%"),
        vol.Required(CONF_GRIFF_OFFEN_POS, default=w[CONF_GRIFF_OFFEN_POS]):
            _zahl(0, 100, 1, "%"),
        _optional(CONF_AZIMUT_VON, w): _zahl(0, 360, 1, "°"),
        _optional(CONF_AZIMUT_BIS, w): _zahl(0, 360, 1, "°"),
        vol.Required(CONF_SPERRE_MIN, default=w[CONF_SPERRE_MIN]):
            _zahl(0, 720, 5, "min"),
        vol.Required(CONF_BLOCK_MORGEN, default=w[CONF_BLOCK_MORGEN]):
            _zahl(0, 240, 5, "min"),
        vol.Required(CONF_BLOCK_ABEND, default=w[CONF_BLOCK_ABEND]):
            _zahl(0, 240, 5, "min"),
        vol.Required(CONF_FROSTSCHUTZ, default=w[CONF_FROSTSCHUTZ]):
            selector.BooleanSelector(),
    })


def _bereinige(daten: dict[str, Any]) -> dict[str, Any]:
    """Zahlen aus dem NumberSelector als int, wo sinnvoll."""
    for key in GANZZAHLEN:
        if daten.get(key) is not None:
            daten[key] = int(daten[key])
    return daten


class RollladenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Legt die Anlage an."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Rollladen", data={},
                options={**_bereinige(user_input), CONF_ROLLLAEDEN: {}},
            )
        return self.async_show_form(
            step_id="user", data_schema=_anlage_schema(self.hass, {}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RollladenOptionsFlow()


class RollladenOptionsFlow(OptionsFlow):
    """Menü: Anlage, Frostschutz, Rollladen hinzufügen/bearbeiten/löschen."""

    def __init__(self) -> None:
        self._rid: str | None = None

    @property
    def _rolllaeden(self) -> dict[str, dict[str, Any]]:
        return dict(self.config_entry.options.get(CONF_ROLLLAEDEN, {}))

    def _speichern(self, *, anlage: dict[str, Any] | None = None,
                   rolllaeden: dict[str, dict[str, Any]] | None = None
                   ) -> ConfigFlowResult:
        optionen = dict(self.config_entry.options)
        if anlage is not None:
            optionen.update(anlage)
        if rolllaeden is not None:
            optionen[CONF_ROLLLAEDEN] = rolllaeden
        return self.async_create_entry(data=optionen)

    def _auswahl(self, mehrfach: bool) -> selector.SelectSelector:
        sortiert = sorted(self._rolllaeden.items(),
                          key=lambda kv: str(kv[1][CONF_NAME]).lower())
        return selector.SelectSelector(selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=rid, label=d[CONF_NAME])
                     for rid, d in sortiert],
            multiple=mehrfach,
            mode=selector.SelectSelectorMode.LIST if mehrfach
            else selector.SelectSelectorMode.DROPDOWN,
        ))

    def _pruefe(self, daten: dict[str, Any], ausser: str | None) -> dict[str, str]:
        fehler: dict[str, str] = {}
        if any(d.get(CONF_COVER) == daten[CONF_COVER]
               for rid, d in self._rolllaeden.items() if rid != ausser):
            fehler[CONF_COVER] = "cover_vergeben"
        von, bis = daten.get(CONF_AZIMUT_VON), daten.get(CONF_AZIMUT_BIS)
        if (von is None) != (bis is None):
            fehler[CONF_AZIMUT_BIS] = "azimut_paar"
        elif von is not None and bis is not None and von >= bis:
            fehler[CONF_AZIMUT_BIS] = "azimut_reihenfolge"
        if daten.get(CONF_TUER) and not daten.get(CONF_GRIFF):
            fehler[CONF_GRIFF] = "tuer_ohne_griff"
        return fehler

    # ---- Schritte -----------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menue = ["anlage", "frost", "rollladen_neu"]
        if self._rolllaeden:
            menue += ["rollladen_bearbeiten", "rollladen_loeschen"]
        return self.async_show_menu(step_id="init", menu_options=menue)

    async def async_step_anlage(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            anlage = _bereinige(user_input)
            # Geleerte optionale Felder wirklich entfernen.
            for key in (CONF_ANWESENHEIT, CONF_TEMPERATUR, CONF_NOTIFY):
                anlage.setdefault(key, None)
            return self._speichern(anlage=anlage)
        return self.async_show_form(
            step_id="anlage",
            data_schema=_anlage_schema(self.hass, dict(self.config_entry.options)))

    async def async_step_frost(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            daten = _bereinige(user_input)
            for key in (CONF_NIEDERSCHLAG, CONF_FEUCHTE, CONF_WETTER):
                daten.setdefault(key, None)
            return self._speichern(anlage=daten)
        return self.async_show_form(
            step_id="frost",
            data_schema=_frost_schema(dict(self.config_entry.options)))

    async def async_step_rollladen_neu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        fehler: dict[str, str] = {}
        if user_input is not None:
            daten = _bereinige(user_input)
            fehler = self._pruefe(daten, None)
            if not fehler:
                rolllaeden = self._rolllaeden
                rolllaeden[ulid_now()] = daten
                return self._speichern(rolllaeden=rolllaeden)
        return self.async_show_form(
            step_id="rollladen_neu",
            data_schema=_rollladen_schema(user_input or {}),
            errors=fehler,
        )

    async def async_step_rollladen_bearbeiten(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._rid = user_input[CONF_AUSWAHL]
            return await self.async_step_rollladen_daten()
        return self.async_show_form(
            step_id="rollladen_bearbeiten",
            data_schema=vol.Schema({vol.Required(CONF_AUSWAHL): self._auswahl(False)}),
        )

    async def async_step_rollladen_daten(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._rid is not None
        fehler: dict[str, str] = {}
        if user_input is not None:
            daten = _bereinige(user_input)
            fehler = self._pruefe(daten, self._rid)
            if not fehler:
                rolllaeden = self._rolllaeden
                rolllaeden[self._rid] = daten
                return self._speichern(rolllaeden=rolllaeden)
        werte = user_input or self._rolllaeden.get(self._rid, {})
        return self.async_show_form(
            step_id="rollladen_daten",
            data_schema=_rollladen_schema(dict(werte)),
            errors=fehler,
            description_placeholders={
                "rollladen": str(self._rolllaeden[self._rid][CONF_NAME])},
        )

    async def async_step_rollladen_loeschen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            rolllaeden = self._rolllaeden
            for rid in user_input.get(CONF_AUSWAHL, []):
                rolllaeden.pop(rid, None)
            return self._speichern(rolllaeden=rolllaeden)
        return self.async_show_form(
            step_id="rollladen_loeschen",
            data_schema=vol.Schema({
                vol.Optional(CONF_AUSWAHL, default=[]): self._auswahl(True)}),
        )
