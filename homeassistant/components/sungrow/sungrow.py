"""Sungrow communication classes."""

import asyncio
import json
import logging
import time
from typing import Any, Final, TypedDict

import aiohttp

RESULT_SUCCESS: Final[int] = 1
RESULT_TOKEN_EXPIRED: Final[int] = 106


class SungrowError(Exception):
    """A superclass that covers all errors from Sungrow devices."""


class TokenExpiredError(SungrowError):
    """Raised when the connection token expires."""


class WiNetInfo(TypedDict):
    """WiNet-s dongle information.

    e.g. {
        'device_sn': 'B2311452938',
        'device_version': 'M_WiNet-S_V01_V01_A',
        'software_version': 'WINET-SV200.001.00.P020',
        'software_build_version': 'WINET-SV200.001.00.B001'
    }
    """

    device_sn: str
    software_version: str
    software_build_version: str
    device_version: str


class SungrowWebsocketClient:
    """Manages the websocket connection to the WiNet-S dongle."""

    # connection: ClientConnection
    token: str = ""
    logger = logging.getLogger("SungrowWebsocketClient")

    session: aiohttp.ClientSession
    _ws: aiohttp.ClientWebSocketResponse

    def __init__(
        self, session: aiohttp.ClientSession, host: str, ws_port: int = 8082
    ) -> None:
        """Initialize the class."""
        self.session = session
        self.host = host
        self.ws_port = ws_port

    async def get_wi_net_info(self) -> WiNetInfo:
        """Get the WiNet-S dongle information."""
        device_sn = ""
        software_version = ""
        software_build_version = ""
        device_version = ""
        result = await self._get(f"http://{self.host}/about/list")
        for row in result["list"]:
            match row["data_name"]:
                case "I18N_COMMON_DEVICE_SN":
                    device_sn = row["data_value"]  # e.g. B2311452938
                case "I18N_COMMON_APPLI_SOFT_VERSION":
                    software_version = row["data_value"]  # e.g. WINET-SV200.001.00.P020
                case "I18N_COMMON_BUILD_SOFT_VERSION":
                    software_build_version = row[
                        "data_value"
                    ]  # e.g. WINET-SV200.001.00.B001
                case "I18N_COMMON_VERSION":
                    device_version = row["data_value"]  # e.g. M_WiNet-S_V01_V01_A
                case _:
                    self.logger.info("Unexpected data %s", row)
        return {
            "device_sn": device_sn,
            "device_version": device_version,
            "software_version": software_version,
            "software_build_version": software_build_version,
        }

    async def get_device_info(self):
        """Get all the available devices and their constants.

        e.g.
            [{"id":	1,
            "dev_id":	1,
            "dev_code":	3599,
            "dev_type":	35,
            "dev_procotol":	2,
            "inv_type":	0,
            "dev_sn":	"A2320600820",
            "dev_name":	"SH10RT(COM1-001)",
            "dev_model":	"SH10RT",
            "port_name":	"COM1",
            "phys_addr":	"1",
            "logc_addr":	"1",
            "link_status":	1,
            "init_status":	1,
            "dev_special":	"0",
            "list":	[]
        },...]
        """
        result = await self._ws_get("devicelist", {"type": "0", "is_check_token": "0"})
        return result["list"]

    async def get_realtime(self, dev_id: int):
        """Get the realtime data from the inverter with a given 'dev_id'.

        data_name                                             data_value     data_unit                en_US
        I18N_COMMON_PV_DAYILY_ENERGY_GENERATION               43.5           kWh                      Daily PV Yield
        I18N_COMMON_PV_TOTAL_ENERGY_GENERATION                192.5          kWh                      Total PV Yield
        I18N_COMMON_TOTAL_YIELD                               --             kWh                      Total Yield
        I18N_COMMON_DEVICE_STATUS                             I18N_COMMON_ENERGY_DISPATCH_OPERATION   Device Status
        I18N_COMMON_BUS_VOLTAGE                               652.0          V                        Bus Voltage
        I18N_COMMON_AIR_TEM_INSIDE_MACHINE                    46.6           ℃                       Internal Air Temperature
        I18N_COMMON_SQUARE_ARRAY_INSULATION_IMPEDANCE         1127           kΩ                       Array Insulation Resistance
        I18N_CONFIG_KEY_1001188                               19.4           %                        Daily Self-consumption Rate
        I18N_COMMON_FEED_NETWORK_TOTAL_ACTIVE_POWER           0.00           kW                       Total Export Active Power
        I18N_CONFIG_KEY_4060                                  0.75           kW                       Purchased Power
        I18N_COMMON_DAILY_FEED_NETWORK_VOLUME                 38.2           kWh                      Daily Feed-in Energy
        I18N_COMMON_TOTAL_FEED_NETWORK_VOLUME                 170.6          kWh                      Total Feed-in Energy
        I18N_COMMON_ENERGY_GET_FROM_GRID_DAILY                6.3            kWh                      Daily Purchased Energy
        I18N_COMMON_TOTAL_ELECTRIC_GRID_GET_POWER             6366.5         kWh                      Total Purchased Energy
        I18N_COMMON_DAILY_FEED_NETWORK_PV                     33.1           kWh                      Daily Feed-in Energy (PV)
        I18N_COMMON_TOTAL_FEED_NETWORK_PV                     142.9          kWh                      Total Feed-in Energy (PV)
        I18N_COMMON_LOAD_TOTAL_ACTIVE_POWER                   0.471          kW                       Total Load Active Power
        I18N_COMMON_DAILY_DIRECT_CONSUMPTION_ELECTRICITY_PV   8.0            kWh                      Daily Load Energy Consumption from PV
        I18N_COMMON_TOTAL_DIRECT_POWER_CONSUMPTION_PV         47.1           kWh                      Total Load Energy Consumption from PV
        I18N_COMMON_TOTAL_DCPOWER                             0.00           kW                       Total DC Power
        I18N_COMMON_TOTAL_ACTIVE_POWER                        -0.28          kW                       Total Active Power
        I18N_COMMON_TOTAL_REACTIVE_POWER                      -0.00          kvar                     Total Reactive Power
        I18N_COMMON_TOTAL_APPARENT_POWER                      0.28           kVA                      Total Apparent Power
        I18N_COMMON_TOTAL_POWER_FACTOR                        1.000                                   Total Power Factor
        I18N_COMMON_GRID_FREQUENCY                            49.99          Hz                       Grid Frequency
        I18N_COMMONUA                                         241.8          V                        Phase A Voltage
        I18N_COMMON_UB                                        242.8          V                        Phase B Voltage
        I18N_COMMON_UC                                        243.0          V                        Phase C Voltage
        I18N_COMMON_FRAGMENT_RUN_TYPE1                        0.8            A                        Phase A Current
        I18N_COMMON_IB                                        0.8            A                        Phase B Current
        I18N_COMMON_IC                                        0.8            A                        Phase C Current
        I18N_COMMON_PHASE_A_BACKUP_CURRENT_QFKYGING           0.3            A                        Phase A Backup Current
        I18N_COMMON_PHASE_B_BACKUP_CURRENT_ODXCTVMS           0.2            A                        Phase B Backup Current
        I18N_COMMON_PHASE_C_BACKUP_CURRENT_PBSQLZIX           0.1            A                        Phase C Backup Current
        I18N_COMMON_PHASE_A_BACKUP_VOLTAGE_PEIYFKXE           --             V                        Phase A Backup Voltage
        I18N_COMMON_PHASE_B_BACKUP_VOLTAGE_MCDGYUJO           --             V                        Phase B Backup Voltage
        I18N_COMMON_PHASE_C_BACKUP_VOLTAGE_SCJZFFCQ           --             V                        Phase C Backup Voltage
        I18N_COMMON_BACKUP_FREQUENCY_MPPOWHDF                 --             HZ                       Backup Frequency
        I18N_COMMON_PHASE_A_BACKUP_POWER_BRBJDGVB             0.000          kW                       Phase A Backup Power
        I18N_COMMON_PHASE_B_BACKUP_POWER_OCDHLMZB             0.000          kW                       Phase B Backup Power
        I18N_COMMON_PHASE_C_BACKUP_POWER_HAMBBGNL             0.000          kW                       Phase C Backup Power
        I18N_COMMON_TOTAL_BACKUP_POWER_WLECIVPM               0.000          kW                       Total Backup Power
        I18N_COMMON_MAXIMUM_APPARENT_POWER_SIWHFGQY           10.0           kVar                     Maximum Apparent Power
        I18N_COMMON_METER_GRID_FREQ_AMMAKPKU                  49.98          Hz                       Meter Grid Freq
        I18N_COMMON_REACTIVE_POWER_UPLOADED_BY_ME_KISYMRKR    -78            var                      Reactive Power Uploaded by Meter
        :param dev_id:
        :return:
        """

        result = await self._ws_get(
            "real", {"dev_id": str(dev_id), "time123456": int(time.time())}
        )
        sensors = {}
        for row in result["list"]:
            sensors[row["data_name"]] = {
                "value": row["data_value"],
                "unit": row["data_unit"],
            }
        return sensors

    async def get_battery_realtime(self, dev_id: int):
        """Get the realtime data from the battery with a given 'dev_id'.

        data_name                             data_value   data_unit   en_US
        I18N_CONFIG_KEY_3907                  0.000        kW          Battery Charging Power
        I18N_CONFIG_KEY_3921                  0.000        kW          Battery Discharging Power
        I18N_COMMON_BATTERY_VOLTAGE           423.5        V           Battery Voltage
        I18N_COMMON_BATTERY_CURRENT           0.0          A           Battery Current
        I18N_COMMON_BATTERY_TEMPERATURE       20.0         ℃          Battery Temperature
        I18N_COMMON_BATTERY_SOC               55.7         %           Battery Level (SOC)
        I18N_COMMON_BATTARY_HEALTH            99.0         %           Battery Health (SOH)
        I18N_COMMON_MAX_CHARGE_CURRENT_BMS    25           A           Max. Charging Current (BMS)
        I18N_COMMON_MAX_DISCHARGE_CURRENT_BMS 25           A           Max. Discharging Current (BMS)
        I18N_COMMON_DAILY_BATTERY_CHARGE_PV   0.0          kWh         Daily Battery Charging Energy from PV
        I18N_COMMON_TOTAL_BATTERY_CHARGE_PV   3.5          kWh         Total Battery Charging Energy from PV
        I18N_COMMON_DAILY_BATTERY_DISCHARGE   0.2          kWh         Daily Battery Discharging Energy
        I18N_COMMON_TOTAL_BATTRY_DISCHARGE    61.6         kWh         Total Battery Discharging Energy
        I18N_COMMON_DAILY_BATTERY_CHARGE      0.0          kWh         Daily Battery Charging Energy
        I18N_COMMON_TOTAL_BATTERY_CHARGE      90.3         kWh         Total Battery Charging Energy
        """

        result = await self._ws_get(
            "real_battery", {"dev_id": str(dev_id), "time123456": int(time.time())}
        )
        sensors = {}
        for row in result["list"]:
            sensors[row["data_name"]] = {
                "value": row["data_value"],
                "unit": row["data_unit"],
            }
        return sensors

    async def close(self):
        """Forcefuly close the underlying connection."""
        if hasattr(self, "_ws"):
            await self._ws.close()

    async def _get(self, url: str) -> dict[str, Any]:
        while True:
            try:
                self.logger.debug("GETting from %s.", url)
                async with self.session.get(url) as resp:
                    if resp.status == 200:
                        response = json.loads(await resp.text())
                        self.logger.debug("Received %s", response)
                        return self._parse_response(response)

                    self.logger.error("%s returned status code %d", url, resp.status)
                    raise SungrowError(
                        f"Unexpected status code {resp.status:d} from {url}."
                    )
            except TokenExpiredError:
                continue  # Hopefully a transient error, retry

    async def _ws_get(self, service: str, params: dict[str, Any]) -> dict[str, Any]:
        while True:
            try:
                await self._ensure_token()

                msg = {"lang": "en_us", "token": self.token, "service": service}
                msg.update(params)

                self.logger.debug("Sending %s", msg)
                await self._ws.send_json(msg)
                response = await self._ws.receive_json()
                self.logger.debug("Received %s", response)

                return self._parse_response(response)
            except TokenExpiredError:
                continue  # Hopefully a transient error, retry
            except ConnectionError as ex:
                self.logger.debug("%s ConnectionError: %s", self._ws.closed, ex)
                await self._ws.close()
                continue

    def _parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        result_code = response.get("result_code", 0)

        if result_code == RESULT_SUCCESS:
            return response["result_data"]

        if result_code == RESULT_TOKEN_EXPIRED:
            self.token = ""
            self.logger.debug(
                "Token Expired: %d:%s", response["result_code"], response["result_msg"]
            )
            raise TokenExpiredError

        self.logger.error(
            "Unknown result: %d:%s", response["result_code"], response["result_msg"]
        )
        raise SungrowError(
            f"Unknown result returned from server: {response['result_code']:d}:{response['result_msg']}"
        )

    async def _ensure_token(self):
        await self._ensure_connected()
        if self.token:
            return

        request = {"lang": "en_us", "token": "", "service": "connect"}
        self.logger.debug("Requesting token with %s.", request)
        await self._ws.send_json(request)
        response = await self._ws.receive_json()

        # { "result_code":	1, "result_msg":	"success", "result_data":	{ "service":	"connect", "token":
        # 		"848a0ca3-b37d-46c1-aa95-921936ee5e87", "uid":	1, "tips_disable":	0 } }
        result_code = response.get("result_code", 0)
        if result_code == RESULT_SUCCESS:
            self.token = response["result_data"]["token"]
            self.logger.debug("Got token %s.", self.token)
            return
        self.logger.error(
            "The 'connect' service responded with result %d:%s",
            response["result_code"],
            response["result_msg"],
        )
        raise SungrowError(
            f"Token request error: {response['result_code']:d}:{response['result_msg']}"
        )

    async def _ensure_connected(self):
        if hasattr(self, "_ws") and not self._ws.closed:
            return

        connection_attempts = 0
        url = "ws://" + self.host + ":" + str(self.ws_port) + "/ws/home/overview"
        while connection_attempts < 10:
            try:
                self.token = ""  # new connection, new token
                self.logger.debug("Opening websocket connection to %s...", url)
                self._ws = await self.session.ws_connect(url)
            except TimeoutError:
                self.logger.info(
                    "Timeout waiting for response from %s. Will retry in 1 second...",
                    url,
                )
                connection_attempts += 1
                await asyncio.sleep(1)
            else:
                self.logger.debug("...connected!")
                return

        self.logger.error(
            "Failed to connect to %s after %d attempts.", url, connection_attempts
        )
        raise SungrowError(
            f"Failed to connect to {url} after {connection_attempts:d} attempts."
        )
