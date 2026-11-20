"""Binärsensoren: Frostschutz aktiv (Anlage), Handsperre und Beschattet
je Rollladen."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    async_add_entities([FrostAktiv(anlage)])
    for r in anlage.sortiert():
        entities: list[BinarySensorEntity] = [Handsperre(anlage, r)]
        if r.beschattbar:
            entities.append(Beschattet(anlage, r))
        async_add_entities(entities)


class FrostAktiv(AnlageEntity, BinarySensorEntity):
    """Frostschutz greift: Schalter an, kalt und nass."""

    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, anlage: Anlage) -> None:
        super().__init__(anlage, "frost_aktiv", "Frostschutz aktiv")

    @property
    def is_on(self) -> bool:
        return self.anlage.frost_aktiv()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        f = self.anlage.frost
        return {
            "kalt": bool(f.get("kalt")),
            "nass": bool(f.get("nass")),
            "grund": f.get("grund"),
            "letzter_niederschlag": f.get("letzter_niederschlag"),
            "letzte_feuchte": f.get("letzte_feuchte"),
        }


class Handsperre(RollladenEntity, BinarySensorEntity):
    _attr_icon = "mdi:hand-back-left"

    def __init__(self, anlage: Anlage, r: Rollladen) -> None:
        super().__init__(anlage, r, "handsperre", "Handsperre")

    @property
    def is_on(self) -> bool:
        return self.anlage.rechner.gesperrt(self.r)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        bis = self.anlage.rechner.sperre_bis(self.r)
        return {"bis": bis.isoformat() if bis else None}


class Beschattet(RollladenEntity, BinarySensorEntity):
    _attr_icon = "mdi:sun-angle"

    def __init__(self, anlage: Anlage, r: Rollladen) -> None:
        super().__init__(anlage, r, "beschattet", "Beschattet")

    @property
    def is_on(self) -> bool:
        return self.r.beschattet

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"grund": self.anlage.rechner.beschattung_grund(self.r)}
