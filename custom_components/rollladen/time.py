"""Uhrzeiten je Rollladen: Zeitfenster für Hoch- und Runterfahrt."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .anlage import Anlage
from .entity import RollladenEntity
from .logik import Rollladen

ZEITEN = (
    ("hoch_frueh", "Hoch frühestens", "mdi:clock-start"),
    ("hoch_spaet", "Hoch spätestens", "mdi:clock-end"),
    ("runter_frueh", "Runter frühestens", "mdi:clock-start"),
    ("runter_spaet", "Runter spätestens", "mdi:clock-end"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    for r in anlage.sortiert():
        async_add_entities(Zeit(anlage, r, key, name, icon)
                           for key, name, icon in ZEITEN)


class Zeit(RollladenEntity, TimeEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, anlage: Anlage, r: Rollladen, key: str, name: str,
                 icon: str) -> None:
        super().__init__(anlage, r, key, name)
        self._key = key
        self._attr_icon = icon

    @property
    def native_value(self) -> time:
        return self.r.zeit(self._key)

    async def async_set_value(self, value: time) -> None:
        self.anlage.setze_wert(self.r, self._key, value.strftime("%H:%M:%S"))
