"""Support for Rivian time entities."""

from __future__ import annotations

from datetime import time
import logging
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_COORDINATOR, ATTR_VEHICLE, DOMAIN
from .coordinator import VehicleCoordinator
from .entity import RivianVehicleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the time entities."""
    data: dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
    vehicles: dict[str, dict[str, Any]] = data[ATTR_VEHICLE]
    coordinators: dict[str, VehicleCoordinator] = data[ATTR_COORDINATOR][ATTR_VEHICLE]

    entities = []
    for vehicle_id, vehicle in vehicles.items():
        coord = coordinators[vehicle_id]
        await coord.get_charging_schedule_data()
        entities.append(RivianChargingScheduleStartTimeEntity(coord, entry, vehicle))
        entities.append(RivianChargingScheduleEndTimeEntity(coord, entry, vehicle))

    async_add_entities(entities)


class RivianChargingScheduleStartTimeEntity(RivianVehicleEntity, TimeEntity):
    """Charging Schedule Start Time Entity."""

    def __init__(
        self,
        coordinator: VehicleCoordinator,
        config_entry: ConfigEntry,
        vehicle: dict[str, Any],
    ) -> None:
        """Construct the start time entity."""
        desc = EntityDescription(
            key="charging_schedule_start",
            name="Charging Schedule Start Time",
            icon="mdi:clock-start",
        )
        super().__init__(coordinator, config_entry, desc, vehicle)

    @property
    def native_value(self) -> time | None:
        """Return native time value."""
        sched = self.coordinator._charging_schedule or {}
        start_mins = sched.get("startTime", 1320)
        return time(hour=(start_mins // 60) % 24, minute=start_mins % 60)

    async def async_set_value(self, value: time) -> None:
        """Set start time value."""
        sched = await self.coordinator.get_charging_schedule_data()
        old_start = sched.get("startTime", 1320)
        old_dur = sched.get("duration", 480)
        old_end = (old_start + old_dur) % 1440

        new_start = value.hour * 60 + value.minute
        new_dur = old_end - new_start
        if new_dur < 0:
            new_dur += 1440

        await self.coordinator.update_charging_schedule_data(
            startTime=new_start, duration=new_dur
        )


class RivianChargingScheduleEndTimeEntity(RivianVehicleEntity, TimeEntity):
    """Charging Schedule End Time Entity."""

    def __init__(
        self,
        coordinator: VehicleCoordinator,
        config_entry: ConfigEntry,
        vehicle: dict[str, Any],
    ) -> None:
        """Construct the end time entity."""
        desc = EntityDescription(
            key="charging_schedule_end",
            name="Charging Schedule End Time",
            icon="mdi:clock-end",
        )
        super().__init__(coordinator, config_entry, desc, vehicle)

    @property
    def native_value(self) -> time | None:
        """Return native time value."""
        sched = self.coordinator._charging_schedule or {}
        start_mins = sched.get("startTime", 1320)
        duration = sched.get("duration", 480)
        end_mins = (start_mins + duration) % 1440
        return time(hour=(end_mins // 60) % 24, minute=end_mins % 60)

    async def async_set_value(self, value: time) -> None:
        """Set end time value."""
        sched = await self.coordinator.get_charging_schedule_data()
        start_mins = sched.get("startTime", 1320)
        end_mins = value.hour * 60 + value.minute

        duration = end_mins - start_mins
        if duration < 0:
            duration += 1440

        await self.coordinator.update_charging_schedule_data(duration=duration)
