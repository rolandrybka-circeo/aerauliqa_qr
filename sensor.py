import logging
import pkg_resources
import yaml
from datetime import timedelta
from homeassistant import config_entries
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import Entity
from pymodbus.client import ModbusTcpClient as ModbusClient
from .config_flow import AerauliqaModbusFlowHandler  # Import the Config Flow Handler
from .const import DOMAIN

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CONF_HOST = "host"
CONF_PORT = "port"

CONF_NAME = "name"
CONF_SLAVE = "slave"
CONF_ADDRESS = "address"
CONF_INPUT_TYPE = "input_type"
CONF_DATA_TYPE = "data_type"
CONF_UNIT_OF_MEASUREMENT = "unit_of_measurement"
CONF_COUNT = "count"
CONF_VALUE_MAP = "value_map"
CONF_WRITABLE = "writable"
CONF_SCALE = "scale"

INPUT_TYPE_HOLDING = "holding"
INPUT_TYPE_INPUT = "input"

DATA_TYPE_UINT32 = "uint32"
DATA_TYPE_UINT16 = "uint16"
DATA_TYPE_FLOAT = "float"

async def async_setup(hass, config):
    """Set up the Aerauliqa Modbus integration."""
    # Check if the configuration is provided via the Home Assistant UI (config flow)
    if DOMAIN in config:
        # Perform any initial setup if needed
        return True

    return True


async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    client = ModbusClient(host=config[CONF_HOST], port=config[CONF_PORT], timeout=10)

    if not client.connect():
        _LOGGER.error("::Modbus Unable to connect to Modbus device at %s:%s", config[CONF_HOST], config[CONF_PORT])
        return

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="aerauliqa_modbus",
        update_method=update_data,
        update_interval=timedelta(seconds=30),
        client=client,
    )

    await coordinator.async_config_entry_first_refresh()

    sensors = []
    with pkg_resources.resource_stream(__name__, "sensors.yaml") as f:
        sensor_configs = yaml.safe_load(f)
        for sensor_config in sensor_configs:
            sensors.append(AerauliqaModbusSensor(coordinator, sensor_config))

    async_add_entities(sensors)

async def update_data(client, config):
    try:
        response = client.read_holding_registers(
            address=config[CONF_ADDRESS],
            count=config[CONF_COUNT],
            unit=config[CONF_SLAVE],
        )

        if response.isError():
            raise UpdateFailed("Modbus error response")

        data = response.registers

        # Calculate the value from the data (implement based on your data type)

        # For example, if the data type is UINT16 (two bytes), combine the two registers:
        if config[CONF_DATA_TYPE] == DATA_TYPE_UINT16:
            numeric_value = data[0]

        # For example, if the data type is UINT32 (four bytes), combine four registers:
        elif config[CONF_DATA_TYPE] == DATA_TYPE_UINT32:
            numeric_value = (data[0] << 16) | data[1]

        # For example, if the data type is FLOAT (four bytes), combine four registers:
        elif config[CONF_DATA_TYPE] == DATA_TYPE_FLOAT:
            numeric_value = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]

        # Add other data types as needed...

        # Convert numeric value to meaningful state using the value_map
        if CONF_VALUE_MAP in config:
            value_map = config[CONF_VALUE_MAP]
            if numeric_value in value_map:
                state = value_map[numeric_value]
            else:
                state = numeric_value
        else:
            state = numeric_value

        return state

    except Exception as ex:
        _LOGGER.error("Error updating data: %s", str(ex))
        raise UpdateFailed("Error updating data")

class AerauliqaModbusSensor(Entity):
    def __init__(self, coordinator, config):
        self._coordinator = coordinator
        self._client = coordinator.client
        self._name = config[CONF_NAME]
        self._slave = config[CONF_SLAVE]
        self._address = config[CONF_ADDRESS]
        self._input_type = config[CONF_INPUT_TYPE]
        self._data_type = config[CONF_DATA_TYPE]
        self._unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT, None)
        self._scale = config.get(CONF_SCALE, None)
        self._count = config[CONF_COUNT]
        self._state = None
        self._value_map = config.get('value_map', {})  # Mapping of numeric values to states
        self._writable = self._input_type == INPUT_TYPE_INPUT

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        if self._state is not None:
            return self._state
        return "Unknown"

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def is_on(self):
        return self._state

    @property
    def should_poll(self):
        return True

    # def update(self):
    #     try:
    #         _LOGGER.debug("::Modbus read holding reg, address: %s, slave: %s", self._address, self._slave)
    #         response = self._client.read_holding_registers(
    #             self._address,
    #             count=self._count,
    #             slave=self._slave
    #         )

    #         if response.isError():
    #             _LOGGER.error("::Modbus error response: %s", str(response))
    #             # self._state = None
    #         else:
    #             data = response.registers  # Read all registers
    #             if self._count == 1:
    #                 numeric_value = data[0]
    #             else:
    #                 # Combine the values from both registers
    #                 numeric_value = (data[0] << 16) | data[1]
    #             if numeric_value in self._value_map:
    #                 self._state = self._value_map[numeric_value]
    #             else:
    #                 if self._scale != None:
    #                     self._state = numeric_value * self._scale
    #                 else:
    #                     self._state = numeric_value
    #     except ConnectionException as ex:
    #         _LOGGER.error("::Modbus connection error: %s", str(ex))
    #         # self._state = None
    # def write_register(self, value):
    #     # Reverse the value_map to obtain numeric value from the selected state
    #     numeric_value = next((k for k, v in self._value_map.items() if v == value), value)

    #     try:
    #         response = self._client.write_register(
    #             address=self._address,
    #             value=numeric_value,
    #             slave=self._slave
    #         )

    #         if response.isError():
    #             _LOGGER.error("Modbus error response: %s", str(response))
    #         else:
    #             _LOGGER.debug("Successfully wrote register: %s", self._address)
    #     except ConnectionException as ex:
    #         _LOGGER.error("Modbus connection error: %s", str(ex))            

    async def async_update(self,config):
        try:
            # Implement the appropriate Modbus read operation based on _input_type and _count
            if self._input_type == INPUT_TYPE_HOLDING:
                response = self._client.read_holding_registers(
                    self._address, count=self._count, unit=self._slave
                )
            else:
                response = self._client.read_input_registers(
                    self._address, count=self._count, unit=self._slave
                )

            if response.isError():
                _LOGGER.error("Modbus error response: %s", str(response))
                raise UpdateFailed("Modbus error response")

            data = response.registers
            if self._count == 1:
                numeric_value = data[0]
            else:
                numeric_value = (data[0] << 16) | data[1]

            # Convert numeric value to meaningful state using the value_map
            if CONF_VALUE_MAP in config:
                value_map = config[CONF_VALUE_MAP]
                if numeric_value in value_map:
                    self._state = value_map[numeric_value]
                else:
                    self._state = numeric_value
            else:
                self._state = numeric_value

        except Exception as ex:
            _LOGGER.error("Error updating data: %s", str(ex))
            raise UpdateFailed("Error updating data")

    async def async_turn_on(self, **kwargs):
        # Implement the write operation for writable registers, if applicable
        if self._writable:
            try:
                # Implement the appropriate Modbus write operation based on _input_type and _count
                # For example, to write a value of 1 to a holding register at address 10:
                response = self._client.write_register(10, 1, unit=self._slave)

                if response.isError():
                    _LOGGER.error("Modbus error response: %s", str(response))
                    return

                # Update the state after writing
                self._state = 1

            except Exception as ex:
                _LOGGER.error("Error writing data: %s", str(ex))

    async def async_turn_off(self, **kwargs):
        # Implement the write operation for writable registers, if applicable
        if self._writable:
            try:
                # Implement the appropriate Modbus write operation based on _input_type and _count
                # For example, to write a value of 0 to a holding register at address 10:
                response = self._client.write_register(10, 0, unit=self._slave)

                if response.isError():
                    _LOGGER.error("Modbus error response: %s", str(response))
                    return

                # Update the state after writing
                self._state = 0

            except Exception as ex:
                _LOGGER.error("Error writing data: %s", str(ex))

config_entries.HANDLERS.register(DOMAIN, AerauliqaModbusFlowHandler, priority=1)
