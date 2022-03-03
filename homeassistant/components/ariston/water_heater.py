"""Water heater entity for Ariston water heaters."""
from datetime import timedelta
import logging
import re

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.water_heater import (
    PLATFORM_SCHEMA,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ariston import Ariston
from .const import DOMAIN, VAL_ECO, VAL_MANUAL, VAL_OFF, VAL_SCHEDULE

ACTION_IDLE = "idle"
ACTION_HEATING = "heating"
UNKNOWN_TEMP = 0.0

SCAN_INTERVAL = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(
            CONF_HOST, default="https://www.ariston-net.remotethermo.com"
        ): cv.string,
    }
)


def camel_to_snake(name):
    """Convert camel case to snake case."""
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ariston water heater devices."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    config = hass.data[DOMAIN][config_entry.entry_id]
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)

    session = async_get_clientsession(hass)

    # Setup connection with devices/cloud
    ariston = Ariston(session, host)
    await ariston.authenticate(username, password)
    plants = await ariston.get_plants()

    async_add_entities([AristonWaterHeater(ariston, plant) for plant in plants], True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Ariston water heater devices."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = config.get(CONF_HOST, "https://www.ariston-net.remotethermo.com")
    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)

    session = async_get_clientsession(hass)

    # Setup connection with devices/cloud
    ariston = Ariston(session, host)
    await ariston.authenticate(username, password)
    plants = await ariston.get_plants()

    async_add_entities([AristonWaterHeater(ariston, plant) for plant in plants], True)


class AristonWaterHeater(WaterHeaterEntity):
    """Ariston Water Heater Device."""

    def __init__(self, ariston, plant_info):
        """Initialize the thermostat."""
        self._ariston: Ariston = ariston
        self._plant_info = plant_info
        self._name = self._plant_info.get("name")
        self._gw = self._plant_info.get("gw")
        self._available = False
        self._plant_data = {}
        self._operation_list = [VAL_OFF, VAL_MANUAL, VAL_SCHEDULE, VAL_ECO]
        self._operation_mode = VAL_OFF
        self._target_temperature = 40
        self._attr_precision = PRECISION_WHOLE

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._name.lower().replace(" ", "_")

    @property
    def name(self) -> str:
        """Return the name of the Climate device."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the name of the Water Heater device."""
        if self.current_operation == VAL_OFF:
            return "mdi:water-off"
        if self.current_operation == VAL_MANUAL:
            return "mdi:water"
        if self.current_operation == VAL_SCHEDULE:
            return "mdi:water-sync"
        if self.current_operation == VAL_ECO:
            return "mdi:water-percent"
        return "mdi:water-off"

    @property
    def should_poll(self) -> bool:
        """Return if polling is required."""
        return True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        features = SUPPORT_TARGET_TEMPERATURE
        if "mode" in self._plant_data:
            features |= SUPPORT_OPERATION_MODE
        return features

    @property
    def current_temperature(self) -> float:
        """Return the temperature."""
        return self._plant_data.get("temp")

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the min temperature."""
        return 40

    @property
    def max_temp(self) -> float:
        """Return the max temperature."""
        return 80

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 1.0

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        return {camel_to_snake(k): v for k, v in self._plant_data.items()}

    @property
    def operation_list(self) -> list[str]:
        """List of available operation modes."""
        return self._operation_list

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        return self._operation_mode

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            try:
                if self._operation_mode == VAL_OFF:
                    await self._ariston.switch(self._gw, True)
                    self._operation_mode = VAL_MANUAL
                await self._ariston.set_temperature(
                    self._gw, new_temperature, self._plant_data.get("eco")
                )
                self._target_temperature = new_temperature
            except Exception as exception:
                self._available = False
                raise Exception from exception
            self.schedule_update_ha_state()

    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if self.current_operation == operation_mode:
            return
        try:
            if self.current_operation == VAL_OFF:
                await self._ariston.switch(self._gw, True)
            if operation_mode == VAL_ECO:
                await self._ariston.switch_eco(self._gw, True)
            elif operation_mode == VAL_SCHEDULE:
                await self._ariston.switch_schedule(self._gw, True)
            elif operation_mode == VAL_MANUAL:
                await self._ariston.switch_schedule(self._gw, False)
            else:
                await self._ariston.switch(self._gw, False)
            self._operation_mode = operation_mode
        except Exception as exception:
            self._available = False
            raise Exception from exception
        self.schedule_update_ha_state()

    async def async_update(self):
        """Update all Node data from Hive."""
        try:
            self._plant_data = await self._ariston.get_plant_data(self._gw)
        except Exception as exception:
            self._available = False
            raise Exception from exception
        self._available = self._plant_data.get("available")
        self._operation_mode = self._get_operation_mode_from_plant_data()
        self._target_temperature = self._plant_data.get("reqTemp")
        self.schedule_update_ha_state()

    def _get_operation_mode_from_plant_data(self):
        if self._plant_data.get("on"):
            if self._plant_data.get("eco"):
                return VAL_ECO
            if self._plant_data.get("mode") == 5:
                return VAL_SCHEDULE
            return VAL_MANUAL
        return VAL_OFF
