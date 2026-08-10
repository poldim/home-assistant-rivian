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

DEFAULT_CHARGING_SCHEDULE_START = 1320
DEFAULT_CHARGING_SCHEDULE_DURATION = 480
MINUTES_PER_DAY = 1440
MINUTES_PER_HOUR = 60


def _get_start_time(coordinator: VehicleCoordinator) -> time:
    """Get start time from schedule coordinator."""
    sched = coordinator._charging_schedule or {}
    start_mins = sched.get("startTime", DEFAULT_CHARGING_SCHEDULE_START)
    return time(
        hour=(start_mins // MINUTES_PER_HOUR) % 24,
        minute=start_mins % MINUTES_PER_HOUR,
    )


def _get_end_time(coordinator: VehicleCoordinator) -> time:
    """Get end time from schedule coordinator."""
    sched = coordinator._charging_schedule or {}
    start_mins = sched.get("startTime", DEFAULT_CHARGING_SCHEDULE_START)
    duration = sched.get("duration", DEFAULT_CHARGING_SCHEDULE_DURATION)
    end_mins = (start_mins + duration) % MINUTES_PER_DAY
    return time(
        hour=(end_mins // MINUTES_PER_HOUR) % 24,
        minute=end_mins % MINUTES_PER_HOUR,
    )


async def _async_set_start_time(coordinator: VehicleCoordinator, value: time) -> None:
    """Set start time for schedule."""
    sched = await coordinator.get_charging_schedule_data()
    old_start = sched.get("startTime", DEFAULT_CHARGING_SCHEDULE_START)
    old_dur = sched.get("duration", DEFAULT_CHARGING_SCHEDULE_DURATION)
    old_end = (old_start + old_dur) % MINUTES_PER_DAY

    new_start = value.hour * MINUTES_PER_HOUR + value.minute
    new_dur = old_end - new_start
    if new_dur <= 0:
        new_dur += MINUTES_PER_DAY

    await coordinator.update_charging_schedule_data(
        startTime=new_start, duration=new_dur
    )


async def _async_set_end_time(coordinator: VehicleCoordinator, value: time) -> None:
    """Set end time for schedule."""
    sched = await coordinator.get_charging_schedule_data()
    start_mins = sched.get("startTime", DEFAULT_CHARGING_SCHEDULE_START)
    end_mins = value.hour * MINUTES_PER_HOUR + value.minute

    duration = end_mins - start_mins
    if duration <= 0:
        duration += MINUTES_PER_DAY

    await coordinator.update_charging_schedule_data(duration=duration)


TIME_ENTITIES: Final[tuple[RivianTimeEntityDescription, ...]] = (
    RivianTimeEntityDescription(
        key="charging_schedule_start",
        translation_key="charging_schedule_start",
        value_fn=_get_start_time,
        set_fn=_async_set_start_time,
    ),
    RivianTimeEntityDescription(
        key="charging_schedule_end",
        translation_key="charging_schedule_end",
        value_fn=_get_end_time,
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
