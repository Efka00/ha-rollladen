"""Zahlen der Anlage: Lux-Schwellen und Frostschwelle."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .anlage import Anlage
from .entity import AnlageEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    async_add_entities([
        AnlageZahl(anlage, "lux_hoch", "Helligkeit hoch ab", "mdi:brightness-6",
                   0, 5000, 10, LIGHT_LUX),
        AnlageZahl(anlage, "lux_runter", "Helligkeit runter unter", "mdi:brightness-4",
                   0, 5000, 10, LIGHT_LUX),
        AnlageZahl(anlage, "frost_schwelle", "Frostschutz unter", "mdi:snowflake-thermometer",
                   -10, 10, 0.5, UnitOfTemperature.CELSIUS),
    ])


class AnlageZahl(AnlageEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, anlage: Anlage, key: str, name: str, icon: str,
                 minimum: float, maximum: float, schritt: float,
                 einheit: str) -> None:
        super().__init__(anlage, key, name)
        self._key = key
        self._attr_icon = icon
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = schritt
        self._attr_native_unit_of_measurement = einheit

    @property
    def native_value(self) -> float:
        return float(self.anlage.a[self._key])

    async def async_set_native_value(self, value: float) -> None:
        self.anlage.setze_anlage(self._key, float(value))
