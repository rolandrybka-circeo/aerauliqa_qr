import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class AerauliqaModbusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Validate the user input here if needed
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("host"): str,
                    vol.Required("port"): int,
                }
            ),
            errors={},
        )

    async def async_step_zeroconf(self, discovery_info):
        return await self.async_step_user()
