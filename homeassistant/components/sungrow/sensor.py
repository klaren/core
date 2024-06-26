"""Support for Sungrow devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    POWER_VOLT_AMPERE_REACTIVE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SUNGROW_DISCOVERY_NEW

if TYPE_CHECKING:
    from . import SungrowConfigEntry
    from .coordinator import (
        SungrowBatteryUpdateCoordinator,
        SungrowCoordinatorBase,
        SungrowInverterUpdateCoordinator,
    )


def dash_zeroes(value: StateType) -> int:
    """Sungrow uses '--' as an indication of no data."""
    if value == "--":
        return 0
    return cast(int, value)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SungrowConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sungrow sensor entities based on a config entry."""
    sungrow_wi_net = config_entry.runtime_data

    for inverter_coordinator in sungrow_wi_net.inverter_coordinators:
        inverter_coordinator.add_entities_for_seen_keys(
            async_add_entities, InverterSensor
        )
    for battery_coordinator in sungrow_wi_net.battery_coordinators:
        battery_coordinator.add_entities_for_seen_keys(
            async_add_entities, BatterySensor
        )

    @callback
    def async_add_new_entities(coordinator: SungrowInverterUpdateCoordinator) -> None:
        """Add newly found inverter entities."""
        coordinator.add_entities_for_seen_keys(async_add_entities, InverterSensor)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SUNGROW_DISCOVERY_NEW,
            async_add_new_entities,
        )
    )


@dataclass(frozen=True)
class SungrowSensorEntityDescription(SensorEntityDescription):
    """Describes Sungorw sensor entity."""

    default_value: StateType | None = None
    # Gen24 devices may report 0 for total energy while doing firmware updates.
    # Handling such values shall mitigate spikes in delta calculations.
    invalid_when_falsy: bool = False
    response_key: str | None = None
    value_fn: Callable[[StateType], StateType] | None = None


INVERTER_ENTITY_DESCRIPTIONS: list[SungrowSensorEntityDescription] = [
    # Inverter
    SungrowSensorEntityDescription(
        key="inverter_temperature_internal_air",
        name="Internal Air Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_AIR_TEM_INSIDE_MACHINE",
    ),
    SungrowSensorEntityDescription(
        key="inverter_maximum_apparent_power",
        name="Maximum Apparent Power",
        native_unit_of_measurement="kVA",
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_MAXIMUM_APPARENT_POWER_SIWHFGQY",
    ),
    SungrowSensorEntityDescription(
        key="inverter_status",
        name="Device Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        response_key="I18N_COMMON_DEVICE_STATUS",
    ),
    # PV
    SungrowSensorEntityDescription(
        key="pv_energy_day",
        name="Daily PV Yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_PV_DAYILY_ENERGY_GENERATION",
    ),
    SungrowSensorEntityDescription(
        key="pv_energy_total",
        name="Total PV Yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_PV_TOTAL_ENERGY_GENERATION",
    ),
    SungrowSensorEntityDescription(
        key="pv_voltage_bus",
        name="Bus Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_BUS_VOLTAGE",
    ),
    SungrowSensorEntityDescription(
        key="pv_insulation_resistance",
        name="Array Insulation Resistance",
        native_unit_of_measurement="kΩ",
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_SQUARE_ARRAY_INSULATION_IMPEDANCE",
    ),
    SungrowSensorEntityDescription(
        key="self_consumption_rate_day",
        name="Daily Self-consumption Rate",
        native_unit_of_measurement=PERCENTAGE,
        response_key="I18N_CONFIG_KEY_1001188",
    ),
    SungrowSensorEntityDescription(
        key="feed_network_active_power",
        name="Total Export Active Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_FEED_NETWORK_TOTAL_ACTIVE_POWER",
    ),
    SungrowSensorEntityDescription(
        key="energy_purchased",
        name="Purchased Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_CONFIG_KEY_4060",
    ),
    SungrowSensorEntityDescription(
        key="feed_network_daily",
        name="Daily Feed-in Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_DAILY_FEED_NETWORK_VOLUME",
    ),
    SungrowSensorEntityDescription(
        key="feed_network_total",
        name="Total Feed-in Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_TOTAL_FEED_NETWORK_VOLUME",
    ),
    SungrowSensorEntityDescription(
        key="grid_purchased_energy_daily",
        name="Daily Purchased Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_ENERGY_GET_FROM_GRID_DAILY",
    ),
    SungrowSensorEntityDescription(
        key="grid_purchased_energy_total",
        name="Total Purchased Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_TOTAL_ELECTRIC_GRID_GET_POWER",
    ),
    SungrowSensorEntityDescription(
        key="pv_feed_network_daily",
        name="Daily Feed-in Energy (PV)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_DAILY_FEED_NETWORK_PV",
    ),
    SungrowSensorEntityDescription(
        key="pv_feed_network_total",
        name="Total Feed-in Energy (PV)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_TOTAL_FEED_NETWORK_PV",
    ),
    SungrowSensorEntityDescription(
        key="total_load_active_power",
        name="Total Load Active Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_LOAD_TOTAL_ACTIVE_POWER",
    ),
    SungrowSensorEntityDescription(
        key="pv_daily_direct_energy_consumption",
        name="Daily Load Energy Consumption from PV",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_DAILY_DIRECT_CONSUMPTION_ELECTRICITY_PV",
    ),
    SungrowSensorEntityDescription(
        key="pv_total_direct_energy_consumption",
        name="Total Load Energy Consumption from PV",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        response_key="I18N_COMMON_TOTAL_DIRECT_POWER_CONSUMPTION_PV",
    ),
    SungrowSensorEntityDescription(
        key="total_dc_power",
        name="Total DC Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_TOTAL_DCPOWER",
    ),
    SungrowSensorEntityDescription(
        key="total_active_power",
        name="Total Active Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_TOTAL_ACTIVE_POWER",
    ),
    SungrowSensorEntityDescription(
        key="total_reactive_power",
        name="Total Reactive Power",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: float(cast(float, value))
        * 1000,  # value is returned as kilo-var
        response_key="I18N_COMMON_TOTAL_REACTIVE_POWER",
    ),
    SungrowSensorEntityDescription(
        key="total_apparent_power",
        name="Total Apparent Power",
        native_unit_of_measurement="kVA",
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_TOTAL_APPARENT_POWER",
    ),
    SungrowSensorEntityDescription(
        key="power_factor_total",
        name="Total Power Factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_TOTAL_POWER_FACTOR",
    ),
    SungrowSensorEntityDescription(
        key="grid_frequency",
        name="Grid Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_GRID_FREQUENCY",
    ),
    SungrowSensorEntityDescription(
        key="voltage_phase_a",
        name="Phase A Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMONUA",
    ),
    SungrowSensorEntityDescription(
        key="voltage_phase_b",
        name="Phase B Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_UB",
    ),
    SungrowSensorEntityDescription(
        key="voltage_phase_c",
        name="Phase C Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_UC",
    ),
    SungrowSensorEntityDescription(
        key="current_phase_a",
        name="Phase A Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_FRAGMENT_RUN_TYPE1",
    ),
    SungrowSensorEntityDescription(
        key="current_phase_b",
        name="Phase B Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_IB",
    ),
    SungrowSensorEntityDescription(
        key="current_phase_c",
        name="Phase C Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_IC",
    ),
    # Backup
    SungrowSensorEntityDescription(
        key="backup_current_phase_a",
        name="Phase A Backup Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_A_BACKUP_CURRENT_QFKYGING",
    ),
    SungrowSensorEntityDescription(
        key="backup_current_phase_b",
        name="Phase B Backup Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_B_BACKUP_CURRENT_ODXCTVMS",
    ),
    SungrowSensorEntityDescription(
        key="backup_current_phase_c",
        name="Phase C Backup Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_C_BACKUP_CURRENT_PBSQLZIX",
    ),
    SungrowSensorEntityDescription(
        key="backup_voltage_phase_a",
        name="Phase A Backup Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_A_BACKUP_VOLTAGE_PEIYFKXE",
        value_fn=dash_zeroes,
    ),
    SungrowSensorEntityDescription(
        key="backup_voltage_phase_b",
        name="Phase B Backup Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_B_BACKUP_VOLTAGE_MCDGYUJO",
        value_fn=dash_zeroes,
    ),
    SungrowSensorEntityDescription(
        key="backup_voltage_phase_c",
        name="Phase C Backup Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_C_BACKUP_VOLTAGE_SCJZFFCQ",
        value_fn=dash_zeroes,
    ),
    SungrowSensorEntityDescription(
        key="backup_frequency",
        name="Backup Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_BACKUP_FREQUENCY_MPPOWHDF",
        value_fn=dash_zeroes,
    ),
    SungrowSensorEntityDescription(
        key="backup_power_phase_a",
        name="Phase A Backup Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_A_BACKUP_POWER_BRBJDGVB",
    ),
    SungrowSensorEntityDescription(
        key="backup_power_phase_b",
        name="Phase B Backup Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_B_BACKUP_POWER_OCDHLMZB",
    ),
    SungrowSensorEntityDescription(
        key="backup_power_phase_c",
        name="Phase C Backup Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_PHASE_C_BACKUP_POWER_HAMBBGNL",
    ),
    SungrowSensorEntityDescription(
        key="backup_power_total",
        name="Total Backup Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_TOTAL_BACKUP_POWER_WLECIVPM",
    ),
    # Meter
    SungrowSensorEntityDescription(
        key="meter_grid_frequency",
        name="Meter Grid Freq",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_METER_GRID_FREQ_AMMAKPKU",
    ),
    SungrowSensorEntityDescription(
        key="meter_reactive_power",
        name="Reactive Power Uploaded by Meter",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_REACTIVE_POWER_UPLOADED_BY_ME_KISYMRKR",
    ),
]

BATTERY_ENTITY_DESCRIPTIONS: list[SungrowSensorEntityDescription] = [
    SungrowSensorEntityDescription(
        key="battery_charging_power",
        name="Battery Charging Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        response_key="I18N_CONFIG_KEY_3907",
    ),
    SungrowSensorEntityDescription(
        key="battery_discharging_power",
        name="Battery Discharging Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        response_key="I18N_CONFIG_KEY_3921",
    ),
    SungrowSensorEntityDescription(
        key="battery_voltage",
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        response_key="I18N_COMMON_BATTERY_VOLTAGE",
    ),
    SungrowSensorEntityDescription(
        key="battery_current",
        name="Battery Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        response_key="I18N_COMMON_BATTERY_CURRENT",
    ),
    SungrowSensorEntityDescription(
        key="battery_temperature",
        name="Battery Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        response_key="I18N_COMMON_BATTERY_TEMPERATURE",
    ),
    SungrowSensorEntityDescription(
        key="battery_soc",
        name="Battery Level (SOC)",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        response_key="I18N_COMMON_BATTERY_SOC",
    ),
    SungrowSensorEntityDescription(
        key="battery_soh",
        name="Battery Health (SOH)",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        response_key="I18N_COMMON_BATTARY_HEALTH",
    ),
    SungrowSensorEntityDescription(
        key="battery_max_charging_current",
        name="Max. Charging Current (BMS)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        response_key="I18N_COMMON_MAX_CHARGE_CURRENT_BMS",
    ),
    SungrowSensorEntityDescription(
        key="battery_max_discharging_current",
        name="Max. Discharging Current (BMS)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        response_key="I18N_COMMON_MAX_DISCHARGE_CURRENT_BMS",
    ),
    SungrowSensorEntityDescription(
        key="battery_charge_pv_daily",
        name="Daily Battery Charging Energy from PV",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        response_key="I18N_COMMON_DAILY_BATTERY_CHARGE_PV",
    ),
    SungrowSensorEntityDescription(
        key="battery_charge_pv_total",
        name="Total Battery Charging Energy from PV",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        response_key="I18N_COMMON_TOTAL_BATTERY_CHARGE_PV",
    ),
    SungrowSensorEntityDescription(
        key="battery_discharge_daily",
        name="Daily Battery Discharging Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        response_key="I18N_COMMON_DAILY_BATTERY_DISCHARGE",
    ),
    SungrowSensorEntityDescription(
        key="battery_discharge_total",
        name="Total Battery Discharging Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        response_key="I18N_COMMON_TOTAL_BATTRY_DISCHARGE",
    ),
    SungrowSensorEntityDescription(
        key="battery_charge_daily",
        name="Daily Battery Charging Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        response_key="I18N_COMMON_DAILY_BATTERY_CHARGE",
    ),
    SungrowSensorEntityDescription(
        key="battery_charge_total",
        name="Total Battery Charging Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        response_key="I18N_COMMON_TOTAL_BATTERY_CHARGE",
    ),
]


class _SungrowSensorEntity(CoordinatorEntity["SungrowCoordinatorBase"], SensorEntity):
    """Defines a Sungrow coordinator entity."""

    entity_description: SungrowSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SungrowCoordinatorBase,
        description: SungrowSensorEntityDescription,
        wi_net_id: str,
    ) -> None:
        """Set up an individual Sungrow meter sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.response_key = description.response_key or description.key
        self.wi_net_id = wi_net_id
        self._attr_native_value = self._get_entity_value()
        self._attr_translation_key = description.key

    def _device_data(self) -> dict[str, Any]:
        """Extract information for SolarNet device from coordinator data."""
        return self.coordinator.data[self.wi_net_id]

    def _get_entity_value(self) -> Any:
        """Extract entity value from coordinator. Raises KeyError if not included in latest update."""
        new_value = self.coordinator.data[self.wi_net_id][self.response_key]["value"]
        if new_value is None:
            return self.entity_description.default_value
        if self.entity_description.invalid_when_falsy and not new_value:
            return None
        if self.entity_description.value_fn is not None:
            new_value = self.entity_description.value_fn(new_value)
        if isinstance(new_value, float):
            return round(new_value, 4)
        return new_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._get_entity_value()
        except KeyError:
            # sets state to `None` if no default_value is defined in entity description
            # KeyError: raised when omitted in response - eg. at night when no production
            self._attr_native_value = self.entity_description.default_value
        self.async_write_ha_state()


class InverterSensor(_SungrowSensorEntity):
    """Defines a Sungrow inverter device sensor entity."""

    def __init__(
        self,
        coordinator: SungrowInverterUpdateCoordinator,
        description: SungrowSensorEntityDescription,
        wi_net_id: str,
    ) -> None:
        """Set up an individual Sungrow inverter sensor."""
        super().__init__(coordinator, description, wi_net_id)
        # device_info created in __init__ from a `GetInverterInfo` request
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = (
            f"{coordinator.inverter_info.device_sn}-{description.key}"
        )


class BatterySensor(_SungrowSensorEntity):
    """Defines a Sungrow battery device sensor entity."""

    def __init__(
        self,
        coordinator: SungrowBatteryUpdateCoordinator,
        description: SungrowSensorEntityDescription,
        wi_net_id: str,
    ) -> None:
        """Set up an individual Sungrow battery sensor."""
        super().__init__(coordinator, description, wi_net_id)

        self._attr_device_info = coordinator.parent_inverter_info.device_info
        self._attr_unique_id = (
            f"{coordinator.parent_inverter_info.device_sn}-{description.key}"
        )
