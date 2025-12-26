"""Example Calendar Integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the example_calendar_integration component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Example Calendar Integration from a config entry."""

    async def add_future_event(call: ServiceCall) -> None:
        """Add a future event to a local calendar."""
        calendar_id = call.data.get("calendar_id")
        summary = call.data.get("summary", "Future Event")
        
        # Create a future event starting 1 hour from now
        start_time = dt_util.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)

        _LOGGER.info("Adding event '%s' to %s at %s", summary, calendar_id, start_time)

        service_data = {
            "entity_id": calendar_id,
            "summary": summary,
            "start_date_time": start_time.isoformat(),
            "end_date_time": end_time.isoformat(),
        }

        await hass.services.async_call(
            "calendar", "create_event", service_data, blocking=True
        )

    hass.services.async_register(DOMAIN, "add_event", add_future_event)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.services.async_remove(DOMAIN, "add_event")
    return True
