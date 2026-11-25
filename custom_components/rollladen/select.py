"""Auswahl je Rollladen: Fahrmodus und Modus (Anwesenheit) je Richtung,
Beschattung."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .anlage import Anlage
from .entity import RollladenEntity
from .logik import ANWESENHEIT, BESCHATTUNG, FAHRMODI, Rollladen

AUSWAHL = (
    ("fahrmodus_hoch", "Fahrmodus hoch", FAHRMODI, "mdi:arrow-up-bold-box-outline"),
    ("fahrmodus_runter", "Fahrmodus runter", FAHRMODI, "mdi:arrow-down-bold-box-outline"),
    ("anwesenheit_hoch", "Modus hoch", ANWESENHEIT, "mdi:account-arrow-up"),
    ("anwesenheit_runter", "Modus runter", ANWESENHEIT, "mdi:account-arrow-down"),
    ("beschattung", "Beschattung", BESCHATTUNG, "mdi:sun-angle-outline"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    for r in anlage.sortiert():
        async_add_entities(
            Auswahl(anlage, r, key, name, optionen, icon)
            for key, name, optionen, icon in AUSWAHL
            # Beschattung nur mit Azimut
            if key != "beschattung" or r.beschattbar
        )


class Auswahl(RollladenEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, anlage: Anlage, r: Rollladen, key: str, name: str,
                 optionen: list[str], icon: str) -> None:
        super().__init__(anlage, r, key, name)
        self._key = key
        self._attr_options = list(optionen)
        self._attr_icon = icon

    @property
    def current_option(self) -> str | None:
        wert = self.r.s.get(self._key)
        return wert if wert in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        self.anlage.setze_wert(self.r, self._key, option)
