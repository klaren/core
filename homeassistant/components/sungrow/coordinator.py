"""DataUpdateCoordinators for the Sungrow integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SungrowDeviceInfo, WiNetId
from .sensor import (
    BATTERY_ENTITY_DESCRIPTIONS,
    INVERTER_ENTITY_DESCRIPTIONS,
    SungrowSensorEntityDescription,
)
from .sungrow import SungrowError

if TYPE_CHECKING:
    from . import SungrowWiNet
    from .sensor import _SungrowSensorEntity


class SungrowCoordinatorBase(ABC, DataUpdateCoordinator[dict[WiNetId, dict[str, Any]]]):
    """Setup."""

    default_interval = timedelta(seconds=30)
    error_interval: timedelta
    valid_descriptions: list[SungrowSensorEntityDescription]

    MAX_FAILED_UPDATES = 3

    def __init__(
        self,
        *args: Any,
        wi_net: SungrowWiNet,
        **kwargs: Any,
    ) -> None:
        """Set up the SungrowCoordinatorBase class."""
        self._failed_update_count = 0
        self.wi_net = wi_net
        # unregistered_descriptors are used to create entities in platform module
        self.unregistered_descriptors: dict[
            WiNetId, list[SungrowSensorEntityDescription]
        ] = {}
        super().__init__(*args, update_interval=self.default_interval, **kwargs)

    @abstractmethod
    async def _update_method(self) -> dict[WiNetId, Any]:
        """Return data per wi net id."""

    async def _async_update_data(self) -> dict[WiNetId, Any]:
        """Fetch the latest data from the source."""
        async with self.wi_net.coordinator_lock:
            try:
                data = await self._update_method()
            except SungrowError as err:
                self._failed_update_count += 1
                if self._failed_update_count == self.MAX_FAILED_UPDATES:
                    self.update_interval = self.error_interval
                raise UpdateFailed(err) from err

            if self._failed_update_count != 0:
                self._failed_update_count = 0
                self.update_interval = self.default_interval

            for wi_net_id in data:
                if wi_net_id not in self.unregistered_descriptors:
                    # id seen for the first time
                    self.unregistered_descriptors[wi_net_id] = (
                        self.valid_descriptions.copy()
                    )
            return data

    @callback
    def add_entities_for_seen_keys[_SungrowEntityT: _SungrowSensorEntity](
        self,
        async_add_entities: AddEntitiesCallback,
        entity_constructor: type[_SungrowEntityT],
    ) -> None:
        """Add entities for received keys and registers listener for future seen keys.

        Called from a platforms `async_setup_entry`.
        """

        @callback
        def _add_entities_for_unregistered_descriptors() -> None:
            """Add entities for keys seen for the first time."""
            new_entities: list[_SungrowEntityT] = []
            for wi_net_id, device_data in self.data.items():
                remaining_unregistered_descriptors = []
                for description in self.unregistered_descriptors[wi_net_id]:
                    key = description.response_key or description.key
                    if key not in device_data:
                        remaining_unregistered_descriptors.append(description)
                        continue
                    if device_data[key]["value"] is None:
                        remaining_unregistered_descriptors.append(description)
                        continue
                    new_entities.append(
                        entity_constructor(
                            coordinator=self,
                            description=description,
                            wi_net_id=wi_net_id,
                        )
                    )
                self.unregistered_descriptors[wi_net_id] = (
                    remaining_unregistered_descriptors
                )
            async_add_entities(new_entities)

        _add_entities_for_unregistered_descriptors()
        self.wi_net.config_entry.async_on_unload(
            self.async_add_listener(_add_entities_for_unregistered_descriptors)
        )


class SungrowInverterUpdateCoordinator(SungrowCoordinatorBase):
    """Query Sungrow device inverter endpoint and keep track of seen conditions."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = INVERTER_ENTITY_DESCRIPTIONS

    SILENT_RETRIES = 3

    def __init__(
        self, *args: Any, inverter_info: SungrowDeviceInfo, **kwargs: Any
    ) -> None:
        """Set up a Sungrow inverter device scope coordinator."""
        super().__init__(*args, **kwargs)
        self.inverter_info = inverter_info

    async def _update_method(self) -> dict[WiNetId, Any]:
        """Return data per wi net id."""
        # almost 1% of `current_inverter_data` requests on Symo devices result in
        # `BadStatusError Code: 8 - LNRequestTimeout` due to flaky internal
        # communication between the logger and the inverter.
        for silent_retry in range(self.SILENT_RETRIES):
            try:
                data = await self.wi_net.sungrow.get_realtime(
                    int(self.inverter_info.wi_net_id)
                )
            except SungrowError:
                if silent_retry == (self.SILENT_RETRIES - 1):
                    raise
                continue
            break
        # wrap a single devices data in a dict with wi_net_id key for
        # SungrowCoordinatorBase _async_update_data and add_entities_for_seen_keys
        return {self.inverter_info.wi_net_id: data}


class SungrowBatteryUpdateCoordinator(SungrowCoordinatorBase):
    """Query Sungrow Batter Management System (BMS)."""

    default_interval = timedelta(minutes=1)
    error_interval = timedelta(minutes=10)
    valid_descriptions = BATTERY_ENTITY_DESCRIPTIONS

    def __init__(
        self, *args: Any, parent_inverter_info: SungrowDeviceInfo, **kwargs: Any
    ) -> None:
        """Set up a Sungrow battery device scope coordinator."""
        super().__init__(*args, **kwargs)
        self.parent_inverter_info = parent_inverter_info

    async def _update_method(self) -> dict[WiNetId, Any]:
        """Return data per wi net id."""
        data = await self.wi_net.sungrow.get_battery_realtime(
            int(self.parent_inverter_info.wi_net_id)
        )
        return {self.parent_inverter_info.wi_net_id: data}
