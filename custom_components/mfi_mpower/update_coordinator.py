"""Update coordinator helpers for the Ubiquiti mFi mPower integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import SLOW_UPDATE_WARNING, DeviceInfo
from homeassistant.helpers.entity_platform import SLOW_SETUP_MAX_WAIT
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import api
from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class MPowerDataUpdateCoordinator(DataUpdateCoordinator):
    """Ubiquiti mFi mPower data update coordinator."""

    def __init__(
        self, hass: HomeAssistant, device: api.MPowerDevice, scan_interval: float
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{NAME} {device.host}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self._api_device = device

    async def _async_update_data(self) -> list[dict]:
        """Fetch data from the device."""
        try:
            updated = self.api_device.updated
            timeout = SLOW_UPDATE_WARNING if updated else SLOW_SETUP_MAX_WAIT
            async with async_timeout.timeout(timeout):
                await api.update_device(self.api_device)
        except asyncio.TimeoutError as exc:
            raise asyncio.TimeoutError(exc) from exc
        except api.MPowerAPIAuthError as exc:
            raise ConfigEntryAuthFailed(exc) from exc
        except Exception as exc:
            raise UpdateFailed(exc) from exc

        return self.api_device.port_data

    @property
    def api_device(self) -> api.MPowerDevice:
        """Return the mFi mPower device from the coordinator."""
        return self._api_device


class MPowerCoordinatorEntity(CoordinatorEntity):
    """Coordinator entity baseclass for Ubiquiti mFi mPower entities."""

    api_entity: api.MPowerEntity
    api_device: api.MPowerDevice

    _attr_assumed_state = False
    _attr_has_entity_name = True

    def __init__(
        self, api_entity: api.MPowerEntity, coordinator: MPowerDataUpdateCoordinator
    ) -> None:
        """Initialize the entity."""
        self.api_entity = api_entity
        self.api_device = api_entity.device
        super().__init__(coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data is not None:
            self.api_entity.data = data[self.api_entity.port - 1]
            self.async_write_ha_state()

    @property
    def skip(self) -> bool:
        """Indicate whether adding of this entity should be skipped."""

        # Skip devices without unique id (for whatever reason)
        if not self.api_device.unique_id:
            return True

        # Skip entities with empty label
        if not self.api_entity.label:
            return True

        return False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        if self.skip:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self.api_entity.unique_id)},
            name=self.api_entity.label,
            manufacturer=self.api_device.manufacturer,
            model=f"{self.api_device.model} Port {self.api_entity.port}",
            via_device=(DOMAIN, self.api_device.unique_id),
        )
