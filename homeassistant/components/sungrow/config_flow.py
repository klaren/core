"""Config flow for Sungrow WiNet-S integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SungrowConfigEntryData
from .sungrow import SungrowError, SungrowWebsocketClient, WiNetInfo

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


def create_title(info: SungrowConfigEntryData) -> str:
    """Return the title of the config flow."""
    return f"Sungrow WiNet-s dongle at {info['host']}"


async def validate_host(
    hass: HomeAssistant, host: str
) -> tuple[str, SungrowConfigEntryData]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    sungrow_websocket = SungrowWebsocketClient(async_get_clientsession(hass), host)

    try:
        info: WiNetInfo = await sungrow_websocket.get_wi_net_info()
    except SungrowError as err:
        _LOGGER.debug(err)
        raise CannotConnect("Unable to connect to the sungrow WiNet-S dongle.") from err
    finally:
        await sungrow_websocket.close()

    return info["device_sn"], SungrowConfigEntryData(host=host)


class SungrowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sungrow WiNet-S dongle."""

    VERSION = 1
    info: SungrowConfigEntryData

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                unique_id, info = await validate_host(self.hass, user_input[CONF_HOST])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates=dict(info))

                return self.async_create_entry(title=create_title(info), data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the DHCP client."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST].removeprefix("http://").rstrip("/").lower() in (
                discovery_info.ip,
                discovery_info.hostname,
            ):
                return self.async_abort(reason="already_configured")

        try:
            unique_id, self.info = await validate_host(self.hass, discovery_info.ip)
        except CannotConnect:
            return self.async_abort(reason="invalid_host")

        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured(updates=dict(self.info))

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to confirm."""
        title = create_title(self.info)
        if user_input is not None:
            return self.async_create_entry(title=title, data=self.info)

        self._set_confirm_only()
        self.context.update({"title_placeholders": {"device": title}})
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "device": title,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
