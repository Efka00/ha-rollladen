"""Gemeinsame Basis der Entities: Anlagen-Gerät und Rollladen-Geräte."""

from __future__ import annotations

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
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


def _bereich(anlage: Anlage, entity_id: str) -> str | None:
    """Bereich des Covers (direkt oder über sein Gerät) als Vorschlag."""
    eintrag = er.async_get(anlage.hass).async_get(entity_id)
    if eintrag is None:
        return None
    area_id = eintrag.area_id
    if area_id is None and eintrag.device_id:
        geraet = dr.async_get(anlage.hass).async_get(eintrag.device_id)
        area_id = geraet.area_id if geraet else None
    if area_id is None:
        return None
    bereich = ar.async_get(anlage.hass).async_get_area(area_id)
    return bereich.name if bereich else None


class RollladenEntity(AnlageEntity):
    """Entity am Gerät eines Rollladens."""

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
            suggested_area=_bereich(anlage, r.cover),
        )
