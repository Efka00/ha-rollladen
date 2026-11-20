"""Sensoren je Rollladen: Status mit Grund, Phase, nächste Fahrten."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .anlage import Anlage
from .entity import RollladenEntity
from .logik import AUF, HOCH, RUNTER, ZU, Rollladen, aus_iso


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    for r in anlage.sortiert():
        async_add_entities([
            Status(anlage, r),
            Cover(anlage, r),
            Phase(anlage, r),
            Naechste(anlage, r, HOCH),
            Naechste(anlage, r, RUNTER),
            Letzte(anlage, r, HOCH),
            Letzte(anlage, r, RUNTER),
        ])


class Status(RollladenEntity, SensorEntity):
    """Was zuletzt passiert ist und warum, dazu alle Details als Attribute."""

    _attr_icon = "mdi:information-outline"

    def __init__(self, anlage: Anlage, r: Rollladen) -> None:
        super().__init__(anlage, r, "status", "Status")

    @property
    def native_value(self) -> str:
        return self.r.grund[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rech = self.anlage.rechner
        sperre = rech.sperre_bis(self.r)
        return {
            "phase": rech.phase(self.r),
            "soll": rech.soll(self.r),
            "position": self.anlage.position(self.r),
            "letzte_position": self.r.s.get("letzte_pos"),
            "griff": self.anlage.griff(self.r) if self.r.griff else None,
            "tuer_sperre": rech.tuer_offen(self.r),
            "handsperre_bis": sperre.isoformat() if sperre else None,
            "blocking": rech.blocking_anzeige(self.r),
            "beschattung": rech.beschattung_grund(self.r)
            if self.r.beschattbar else None,
            "frostschutz": rech.frost_greift(self.r),
        }


class Cover(RollladenEntity, SensorEntity):
    """Welches Cover dieser Rollladen steuert, Griff, Taster und die letzten
    Befehle der Integration (Automatik und Taster, neueste zuerst)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:window-shutter-cog"
    _unrecorded_attributes = frozenset({"protokoll"})

    def __init__(self, anlage: Anlage, r: Rollladen) -> None:
        super().__init__(anlage, r, "cover", "Cover")

    @property
    def native_value(self) -> str:
        return self.r.cover

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self.hass.states.get(self.r.cover)
        protokoll = self.r.s.get("protokoll") or []
        return {
            "name": st.name if st else None,
            "griff": self.r.griff,
            "taster": self.r.taster,
            "letzter_befehl": protokoll[0] if protokoll else None,
            "protokoll": protokoll,
        }


class Phase(RollladenEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [AUF, ZU]
    _attr_icon = "mdi:theme-light-dark"

    def __init__(self, anlage: Anlage, r: Rollladen) -> None:
        super().__init__(anlage, r, "phase", "Phase")

    @property
    def native_value(self) -> str:
        return self.anlage.rechner.phase(self.r)


class Naechste(RollladenEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, anlage: Anlage, r: Rollladen, richtung: str) -> None:
        name = "Nächste Hochfahrt" if richtung == HOCH else "Nächste Runterfahrt"
        super().__init__(anlage, r, f"naechste_{richtung}", name)
        self._richtung = richtung
        self._attr_icon = ("mdi:arrow-up-bold-circle-outline" if richtung == HOCH
                           else "mdi:arrow-down-bold-circle-outline")

    @property
    def native_value(self) -> datetime:
        return self.anlage.rechner.naechste(self.r, self._richtung)


class Letzte(RollladenEntity, SensorEntity):
    """Letzte Tagesfahrt dieser Richtung (Tages-Merker)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, anlage: Anlage, r: Rollladen, richtung: str) -> None:
        name = "Letzte Hochfahrt" if richtung == HOCH else "Letzte Runterfahrt"
        super().__init__(anlage, r, f"letzte_{richtung}", name)
        self._richtung = richtung
        self._attr_icon = "mdi:history"

    @property
    def native_value(self) -> datetime | None:
        return aus_iso(self.r.s.get("letzte_" + self._richtung))
