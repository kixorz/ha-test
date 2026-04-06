"""Local Calendar Status Example Integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the local_calendar_status component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Local Calendar Status Example from a config entry."""

    async def get_next_event(call: ServiceCall) -> ServiceResponse:
        """Get the next event from a local calendar."""
        calendar_id = call.data.get("calendar_id")
        
        # Look for events in the next 24 hours
        start_time = dt_util.now()
        end_time = start_time + timedelta(hours=24)

        _LOGGER.info("Fetching next event from %s", calendar_id)

        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": calendar_id,
                "start_date_time": start_time.isoformat(),
                "end_date_time": end_time.isoformat(),
            },
            blocking=True,
            return_response=True,
        )

        return response

    hass.services.async_register(
        DOMAIN, 
        "get_next_event", 
        get_next_event,
        supports_response=SupportsResponse.ONLY,
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.services.async_remove(DOMAIN, "get_next_event")
    return True
