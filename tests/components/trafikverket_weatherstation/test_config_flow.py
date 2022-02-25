"""Test the Trafikverket weatherstation config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from tests.common import MockConfigEntry

DOMAIN = "trafikverket_weatherstation"
CONF_STATION = "station"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
    ), patch(
        "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Vallby"
    assert result2["data"] == {
        "api_key": "1234567890",
        "station": "Vallby",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
    ), patch(
        "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: "Vallby",
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Vallby"
    assert result2["data"] == {
        "api_key": "1234567890",
        "station": "Vallby",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_STATION: "Vallby",
        },
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: "Vallby",
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "abort"
    assert result3["reason"] == "already_configured"


@pytest.mark.parametrize(
    "error_message,base_error",
    [
        (
            "Source: Security, message: Invalid authentication",
            "invalid_auth",
        ),
        (
            "Could not find a weather station with the specified name",
            "invalid_station",
        ),
        (
            "Found multiple weather stations with the specified name",
            "more_stations",
        ),
        (
            "Unknown",
            "cannot_connect",
        ),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, error_message: str, base_error: str
) -> None:
    """Test config flow errors."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == RESULT_TYPE_FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
        side_effect=ValueError(error_message),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )

    assert result4["errors"] == {"base": base_error}
