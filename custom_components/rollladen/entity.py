"""Gemeinsame Basis der Entities: Anlagen-Gerät und Rollladen-Geräte."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .anlage import Anlage
from .const import DOMAIN
from .logik import Rollladen


class AnlageEntity(Entity):
    """Entity am Gerät „Rollladen“."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, anlage: Anlage, key: str, name: str) -> None:
        self.anlage = anlage
        entry_id = anlage.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Rollladen",
            manufacturer="ha-rollladen",
            model="Anlage",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.anlage.async_add_listener(self.async_write_ha_state))


class RollladenEntity(AnlageEntity):
    """Entity am Gerät eines Rollladens.

    Bewusst ohne ``suggested_area``: Home Assistant setzt den Bereich sonst
    vor jede Entity-ID (``abstellkammer_abstellkammer_automatik``). Den
    Bereich trägt ``Anlage.bereiche_setzen`` nach, wenn die IDs stehen."""

    def __init__(self, anlage: Anlage, r: Rollladen, key: str, name: str) -> None:
        super().__init__(anlage, key, name)
        self.r = r
        self._attr_unique_id = f"{r.id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, r.id)},
            name=r.name,
            manufacturer="ha-rollladen",
            model="Rollladen",
            via_device_id=anlage.geraet_id,
        )
