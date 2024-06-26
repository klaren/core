"""The Sungrow WiNet-S integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    SUNGROW_DISCOVERY_NEW,
    SUNGROW_RESCAN_TIMER,
    SungrowDeviceInfo,
    SungrowDeviceType,
    get_device_type,
)
from .coordinator import (
    SungrowBatteryUpdateCoordinator,
    SungrowInverterUpdateCoordinator,
)
from .sungrow import SungrowError, SungrowWebsocketClient, WiNetInfo

_LOGGER: Final = logging.getLogger(__name__)
PLATFORMS: Final = [Platform.SENSOR]

type SungrowConfigEntry = ConfigEntry[SungrowWiNet]


async def async_setup_entry(hass: HomeAssistant, entry: SungrowConfigEntry) -> bool:
    """Set up Sungrow WiNet from a config entry."""

    host = entry.data[CONF_HOST]
    sungrow_websocket = SungrowWebsocketClient(async_get_clientsession(hass), host)
    wi_net = SungrowWiNet(hass, entry, sungrow_websocket)
    await wi_net.init_devices()

    entry.runtime_data = wi_net
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SungrowConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        wi_net = entry.runtime_data
        await wi_net.sungrow.close()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


class SungrowWiNet:
    """The SungrowWiNet class routes..."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, sungrow: SungrowWebsocketClient
    ) -> None:
        """Initialize SungrowWiNetClass."""
        self.hass = hass
        self.config_entry = entry
        self.coordinator_lock = asyncio.Lock()
        self.sungrow: SungrowWebsocketClient = sungrow
        self.host: str = entry.data[CONF_HOST]
        self.system_device_info: DeviceInfo | None = None

        self.inverter_coordinators: list[SungrowInverterUpdateCoordinator] = []
        self.battery_coordinators: list[SungrowBatteryUpdateCoordinator] = []

    async def init_devices(self) -> None:
        """Initialize DataUpdateCoordinators for Sungrow WiNet devices."""

        self.system_device_info = await self._create_wi_net_device()

        await self._init_devices_inverter()

        # Setup periodic re-scan
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._init_devices_inverter,
                timedelta(minutes=SUNGROW_RESCAN_TIMER),
            )
        )

    async def _create_wi_net_device(self) -> DeviceInfo:
        """Create a device for the WiNet-S dongel."""
        info: WiNetInfo = await self.sungrow.get_wi_net_info()
        wi_net_device: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, info["device_sn"])},
            manufacturer="Sungrow",
            name="WiNet-S LAN Communication Module",
            model=info["device_version"],
            sw_version=info["software_version"],
            serial_number=info["device_sn"],
        )

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            **wi_net_device,
        )
        return wi_net_device

    async def _init_devices_inverter(self, _now: datetime | None = None) -> None:
        """Get available inverters and set up coordinators for new found devices."""
        _inverter_infos = await self._get_inverter_infos()

        _LOGGER.debug("Processing inverters for: %s", _inverter_infos)
        for _inverter_info in _inverter_infos:
            _inverter_name = f"{DOMAIN}_inverter_{_inverter_info.wi_net_id}_{self.host}"

            # Add found inverter only not already existing
            if _inverter_info.device_sn in [
                inv.inverter_info.device_sn for inv in self.inverter_coordinators
            ]:
                continue

            _coordinator = SungrowInverterUpdateCoordinator(
                hass=self.hass,
                wi_net=self,
                logger=_LOGGER,
                name=_inverter_name,
                inverter_info=_inverter_info,
            )
            await _coordinator.async_config_entry_first_refresh()
            self.inverter_coordinators.append(_coordinator)

            # Only for re-scans. Initial setup adds entities through sensor.async_setup_entry
            if self.config_entry.state == ConfigEntryState.LOADED:
                async_dispatcher_send(self.hass, SUNGROW_DISCOVERY_NEW, _coordinator)

            _LOGGER.debug(
                "New inverter added (ID: %s, SN: %s)",
                _inverter_info.wi_net_id,
                _inverter_info.device_sn,
            )

            if _inverter_info.device_type == SungrowDeviceType.HYBRID_INVERTER:
                _battery_coordinator = SungrowBatteryUpdateCoordinator(
                    hass=self.hass,
                    wi_net=self,
                    logger=_LOGGER,
                    name=f"{DOMAIN}_battery_{_inverter_info.wi_net_id}_{self.host}",
                    parent_inverter_info=_inverter_info,
                )
                await _battery_coordinator.async_config_entry_first_refresh()
                self.battery_coordinators.append(_battery_coordinator)

                _LOGGER.debug(
                    "New battery added (ID: %s, Inverter ID: %s)",
                    _inverter_info.wi_net_id,
                    _inverter_info.device_sn,
                )

    async def _get_inverter_infos(self) -> list[SungrowDeviceInfo]:
        """Get information about the inverters in the SolarNet system."""
        inverter_infos: list[SungrowDeviceInfo] = []

        try:
            _inverter_list = await self.sungrow.get_device_info()
        except SungrowError as err:
            if self.config_entry.state == ConfigEntryState.LOADED:
                # During a re-scan we will attempt again as per schedule.
                _LOGGER.debug("Re-scan failed for %s", self.host)
                return inverter_infos

            raise ConfigEntryNotReady from err

        # 		"list":	[{
        # 				"id":	1,
        # 				"dev_id":	1,
        # 				"dev_code":	3599,
        # 				"dev_type":	35,
        # 				"dev_procotol":	2,
        # 				"inv_type":	0,
        # 				"dev_sn":	"A2320857820",
        # 				"dev_name":	"SH10RT(COM1-001)",
        # 				"dev_model":	"SH10RT",
        # 				"port_name":	"COM1",
        # 				"phys_addr":	"1",
        # 				"logc_addr":	"1",
        # 				"link_status":	1,
        # 				"init_status":	1,
        # 				"dev_special":	"0",
        # 				"list":	[]
        # 			}],

        for inverter in _inverter_list:
            device_id = inverter["dev_id"]
            device_sn = inverter["dev_sn"]
            device_type = get_device_type(inverter["dev_type"])

            device_info = DeviceInfo(
                identifiers={(DOMAIN, device_sn)},
                manufacturer="Sungrow",
                model=inverter["dev_model"],
                name=inverter["dev_name"],
                serial_number=device_sn,
            )
            inverter_infos.append(
                SungrowDeviceInfo(
                    device_info=device_info,
                    wi_net_id=device_id,
                    device_sn=device_sn,
                    device_type=device_type,
                )
            )
            _LOGGER.debug(
                "Inverter found at %s (Device ID: %s, SN: %s)",
                self.host,
                device_id,
                device_sn,
            )
        return inverter_infos
