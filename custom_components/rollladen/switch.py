"""Schalter: Automatik, Beschattung, Frostschutz (Anlage), Automatik je
Rollladen."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .anlage import Anlage
from .entity import AnlageEntity, RollladenEntity
from .logik import Rollladen


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    async_add_entities([
        AnlageSchalter(anlage, "automatik", "Automatik", "mdi:window-shutter-auto"),
        AnlageSchalter(anlage, "beschattung", "Beschattung", "mdi:sun-wireless"),
        AnlageSchalter(anlage, "frostschutz", "Frostschutz", "mdi:snowflake-alert"),
    ])
    async_add_entities(RollladenAutomatik(anlage, r) for r in anlage.sortiert())


class AnlageSchalter(AnlageEntity, SwitchEntity):
    """Automatik: Hauptschalter für alle Rollläden. Beschattung und
    Frostschutz: global an/aus, je Rollladen fein über dessen Einstellungen."""

    def __init__(self, anlage: Anlage, key: str, name: str, icon: str) -> None:
        super().__init__(anlage, key, name)
        self._key = key
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return bool(self.anlage.a[self._key])

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.anlage.setze_anlage(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.anlage.setze_anlage(self._key, False)


class RollladenAutomatik(RollladenEntity, SwitchEntity):
    """Automatik dieses Rollladens. Aus = nur noch Taster und Hand."""

    _attr_icon = "mdi:window-shutter-auto"

    def __init__(self, anlage: Anlage, r: Rollladen) -> None:
        super().__init__(anlage, r, "automatik", "Automatik")

    @property
    def is_on(self) -> bool:
        return self.r.automatik

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.anlage.setze_wert(self.r, "automatik", True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Eine laufende Handsperre gehört zur Automatik und endet mit ihr.
        self.r.s["sperre_bis"] = None
        self.r.s["beschattet"] = False
        self.anlage.setze_wert(self.r, "automatik", False)
