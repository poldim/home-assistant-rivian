"""Support for Rivian time entities."""

from __future__ import annotations

from datetime import time
import logging
from typing import Final, Any

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_COORDINATOR, ATTR_VEHICLE, DOMAIN
from .coordinator import VehicleCoordinator
from .data_classes import RivianTimeEntityDescription
from .entity import RivianVehicleEntity

_LOGGER = logging.getLogger(__name__)


async def _async_set_start_time(coordinator: VehicleCoordinator, value: time) -> None:
    """Set start time for schedule."""
    sched = await coordinator.get_charging_schedule_data()
    old_start = sched.get("startTime", 1320)
    old_dur = sched.get("duration", 480)
    old_end = (old_start + old_dur) % 1440

    new_start = value.hour * 60 + value.minute
    new_dur = old_end - new_start
    if new_dur <= 0:
        new_dur += 1440

    await coordinator.update_charging_schedule_data(
        startTime=new_start, duration=new_dur
    )


async def _async_set_end_time(coordinator: VehicleCoordinator, value: time) -> None:
    """Set end time for schedule."""
    sched = await coordinator.get_charging_schedule_data()
    start_mins = sched.get("startTime", 1320)
    end_mins = value.hour * 60 + value.minute

    duration = end_mins - start_mins
    if duration <= 0:
        duration += 1440

    await coordinator.update_charging_schedule_data(duration=duration)


TIME_ENTITIES: Final[tuple[RivianTimeEntityDescription, ...]] = (
    RivianTimeEntityDescription(
        key="charging_schedule_start",
        name="Charging Schedule Start Time",
        translation_key="charging_schedule_start",
        value_fn=lambda c: (
            time(
                hour=((c._charging_schedule or {}).get("startTime", 1320) // 60) % 24,
                minute=(c._charging_schedule or {}).get("startTime", 1320) % 60,
            )
        ),
        set_fn=_async_set_start_time,
    ),
    RivianTimeEntityDescription(
        key="charging_schedule_end",
        name="Charging Schedule End Time",
        translation_key="charging_schedule_end",
        value_fn=lambda c: (
            time(
                hour=(
                    (
                        (c._charging_schedule or {}).get("startTime", 1320)
                        + (c._charging_schedule or {}).get("duration", 480)
                    )
                    // 60
                )
                % 24,
                minute=(
                    (c._charging_schedule or {}).get("startTime", 1320)
                    + (c._charging_schedule or {}).get("duration", 480)
                )
                % 60,
            )
        ),
        set_fn=_async_set_end_time,
    ),
)


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
        for description in TIME_ENTITIES:
            entities.append(
                RivianChargingScheduleTimeEntity(coord, entry, description, vehicle)
            )

    async_add_entities(entities)


class RivianChargingScheduleTimeEntity(RivianVehicleEntity, TimeEntity):
    """Charging Schedule Time Entity."""

    entity_description: RivianTimeEntityDescription

    def __init__(
        self,
        coordinator: VehicleCoordinator,
        config_entry: ConfigEntry,
        description: RivianTimeEntityDescription,
        vehicle: dict[str, Any],
    ) -> None:
        """Construct the charging schedule time entity."""
        super().__init__(coordinator, config_entry, description, vehicle)

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._available

    @property
    def native_value(self) -> time | None:
        """Return native time value."""
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_value(self, value: time) -> None:
        """Set time value."""
        await self.entity_description.set_fn(self.coordinator, value)
