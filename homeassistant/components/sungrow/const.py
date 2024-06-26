"""Constants for the Sungrow WiNet-S integration."""

from enum import StrEnum
from typing import Final, NamedTuple, TypedDict

from homeassistant.helpers.device_registry import DeviceInfo

DOMAIN: Final = "sungrow"

type WiNetId = str
SUNGROW_DISCOVERY_NEW: Final = "sungrow_discovery_new"
SUNGROW_RESCAN_TIMER: Final = 60


class SungrowConfigEntryData(TypedDict):
    """ConfigEntry for the Sungrow integration."""

    host: str


class SungrowDeviceType(StrEnum):
    """Inverter type."""

    STRING_INVERTER = "string_inverter"
    HYBRID_INVERTER = "hybrid_inverter"
    UNKNOWN = "unknown"


def get_device_type(code: int) -> SungrowDeviceType:
    """Get the device type from the given code."""
    # Device Type, 21 = PV Inverter, 35 = Hybrid Inverter
    match code:
        case 21:
            return SungrowDeviceType.STRING_INVERTER
        case 35:
            return SungrowDeviceType.HYBRID_INVERTER
    return SungrowDeviceType.UNKNOWN


class SungrowDeviceInfo(NamedTuple):
    """Information about a Sungrow inverter device."""

    device_info: DeviceInfo
    wi_net_id: WiNetId
    device_sn: str
    device_type: SungrowDeviceType
