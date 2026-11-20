"""Rollladen – Steuerung von Rollläden mit Automatik, Beschattung und Tastern."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .anlage import Anlage
from .const import DOMAIN

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

type RollladenConfigEntry = ConfigEntry[Anlage]


async def async_setup_entry(hass: HomeAssistant,
                            entry: RollladenConfigEntry) -> bool:
    """Anlage einrichten."""
    anlage = Anlage(hass, entry)
    await anlage.async_laden()
    # Anlagen-Gerät vorab anlegen: die Rollladen-Geräte verweisen darauf.
    dev_reg = dr.async_get(hass)
    geraet = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Rollladen",
        manufacturer="ha-rollladen",
        model="Anlage",
    )
    anlage.geraet_id = geraet.id
    # Geräte gelöschter Rollläden entfernen (ihre Entities gehen mit).
    gueltig = {entry.entry_id, *anlage.rolllaeden}
    for alt in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        kennungen = {k for d, k in alt.identifiers if d == DOMAIN}
        if kennungen and not kennungen & gueltig:
            dev_reg.async_remove_device(alt.id)
    entry.runtime_data = anlage
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    anlage.async_start()
    # Optionen geändert oder Rollladen hinzugefügt/bearbeitet/gelöscht.
    entry.async_on_unload(entry.add_update_listener(_neu_laden))
    return True


async def async_unload_entry(hass: HomeAssistant,
                             entry: RollladenConfigEntry) -> bool:
    """Anlage entladen. Der Zustand ist gespeichert."""
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _neu_laden(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
