import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required('host'): str,
    vol.Required('port'): int,
    vol.Required('sensors'): vol.All(),
})

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    name = config[CONF_NAME]
    host = config['host']
    port = config['port']
    sensors = config['sensors']
    try:
        client = ModbusTcpClient(host, port)
        client.connect()
        _LOGGER.debug("::Modbus connection OK! %s:%s", host, port)
    except ConnectionException as ex:
        _LOGGER.error("::Error connecting to Modbus device: %s", str(ex))
        return

    modbus_sensors = []
    for sensor in sensors:
        modbus_sensor = AerauliqaQRSensor(client, sensor)
        modbus_sensors.append(modbus_sensor)
        if modbus_sensor._input_type == 'input':
            _LOGGER.debug("::Modbus add write service %s", modbus_sensor._name)
            async def handle_write_service(call):
                state = call.data.get("state")
                if state is not None:
                    await modbus_sensor.async_set_state(state)
            hass.services.async_register("aerauliqa_qr", modbus_sensor.service_name + "_write", handle_write_service)

    add_entities(modbus_sensors)

class AerauliqaQRSensor(Entity):
    def __init__(self, client, config):
        self.entity_id = config.get('entity_id', None);
        self.service_name = config.get('service_name', None);
        self._client = client
        self._name = config['name']
        self._slave = config['slave']
        self._address = config['address']
        self._input_type = config['input_type']
        self._data_type = config['data_type']
        self._unit_of_measurement = config.get('unit_of_measurement', None)
        self._scale = config.get('scale', None)
        self._count = config['count']
        self._state = None
        self._value_map = config.get('value_map', {})  # Mapping of numeric values to states

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return 'uq_' + self.entity_id

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._input_type == "input":
            _LOGGER.debug("::Modbus register %s is input", self._name)
            return 1
        _LOGGER.debug("::Modbus register %s is read only", self._name)
        return 0
    
    @property
    def state(self):
        if self._state is not None:
            return self._state
        return "Unknown"

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    def update(self):
        try:
            _LOGGER.debug("::Modbus read holding reg, address: %s, slave: %s", self._address, self._slave)
            response = self._client.read_holding_registers(
                self._address,
                count=self._count,
                slave=self._slave
            )

            if response.isError():
                _LOGGER.error("::Modbus error response: %s", str(response))
                # self._state = None
            else:
                data = response.registers  # Read all registers
                if self._count == 1:
                    numeric_value = data[0]
                else:
                    # Combine the values from both registers
                    numeric_value = (data[0] << 16) | data[1]
                if numeric_value in self._value_map:
                    self._state = self._value_map[numeric_value]
                else:
                    if self._scale != None:
                        self._state = numeric_value * self._scale
                    else:
                        self._state = numeric_value
        except ConnectionException as ex:
            _LOGGER.error("::Modbus connection error: %s", str(ex))
            # self._state = None
    def write_register(self, value):
        # Reverse the value_map to obtain numeric value from the selected state
        numeric_value = next((k for k, v in self._value_map.items() if v == value), value)
        _LOGGER.error("::Modbus write register of: %s to %s", self._name, numeric_value)

        try:
            response = self._client.write_register(
                address=self._address,
                value=numeric_value,
                slave=self._slave
            )

            if response.isError():
                _LOGGER.error("Modbus error response: %s", str(response))
            else:
                _LOGGER.debug("Successfully wrote register: %s", self._address)
        except ConnectionException as ex:
            _LOGGER.error("Modbus connection error: %s", str(ex))            

    async def async_set_state(self, state):
        _LOGGER.error("::Modbus set state of: %s to %s", self._name, state)
        if self._input_type == "input":
            # Call the write_register method to write the value
            self.write_register(state)
            # Update the internal state to reflect the change
            self._state = state
            # Notify Home Assistant that the state has changed
            self.async_write_ha_state()
        else:
            _LOGGER.warning("This entity is read-only and cannot be modified.")
