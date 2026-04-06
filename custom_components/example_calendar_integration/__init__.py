"""Example Calendar Integration."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# External API — returns todo items used as calendar event content
_TODOS_API_URL = "https://jsonplaceholder.typicode.com/todos"

# Day schedule: 6 back-to-back 2-hour slots starting at 08:00
_EVENT_COUNT = 6
_DAY_START_HOUR = 8
_SLOT_DURATION_HOURS = 2

# HA bus event name fired at each calendar event's start time
EVENT_START_FIRED = f"{DOMAIN}_event_start"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the example_calendar_integration component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Example Calendar Integration from a config entry."""

    # Track all scheduled listener cancel callbacks so we can clean up on unload
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("cancel_listeners", [])

    async def fill_day_with_events(call: ServiceCall) -> None:
        """Fetch 6 todos from JSONPlaceholder, fill a calendar day, and schedule triggers."""
        calendar_id: str = call.data["calendar_id"]

        # Resolve target date — defaults to today in HA's local timezone
        raw_date = call.data.get("target_date")
        if raw_date:
            target_date: date = (
                raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date))
            )
        else:
            target_date = dt_util.now().date()

        _LOGGER.info(
            "Filling calendar '%s' for %s with %d events from JSONPlaceholder",
            calendar_id,
            target_date,
            _EVENT_COUNT,
        )

        # --- Fetch todos from the external API ---
        session = async_get_clientsession(hass)
        try:
            import aiohttp  # noqa: PLC0415

            async with session.get(
                _TODOS_API_URL,
                params={"_limit": _EVENT_COUNT},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                todos: list[dict[str, Any]] = await response.json()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to fetch todos from %s: %s", _TODOS_API_URL, err)
            return

        if not todos:
            _LOGGER.warning("API returned no todos; aborting.")
            return

        tz = dt_util.get_default_time_zone()
        now = dt_util.now()

        # --- Create calendar events and schedule start-time triggers ---
        for index, todo in enumerate(todos[:_EVENT_COUNT]):
            slot_start_hour = _DAY_START_HOUR + index * _SLOT_DURATION_HOURS
            start_dt = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                slot_start_hour,
                0,
                0,
                tzinfo=tz,
            )
            end_dt = start_dt + timedelta(hours=_SLOT_DURATION_HOURS)

            summary = todo.get("title", f"Event {index + 1}")
            completed = todo.get("completed", False)
            todo_id = todo.get("id", index + 1)
            description = (
                f"Source: JSONPlaceholder todo #{todo_id}\n"
                f"Status: {'Completed' if completed else 'Pending'}"
            )

            _LOGGER.debug(
                "Creating event %d/%d: '%s' at %s–%s",
                index + 1,
                _EVENT_COUNT,
                summary,
                start_dt.isoformat(),
                end_dt.isoformat(),
            )

            # Create the calendar event
            await hass.services.async_call(
                "calendar",
                "create_event",
                {
                    "entity_id": calendar_id,
                    "summary": summary,
                    "description": description,
                    "start_date_time": start_dt.isoformat(),
                    "end_date_time": end_dt.isoformat(),
                },
                blocking=True,
            )

            # Schedule a trigger at the event's start time (skip if already past)
            if start_dt > now:
                _schedule_event_trigger(
                    hass,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    summary=summary,
                    description=description,
                    calendar_id=calendar_id,
                )
            else:
                _LOGGER.debug(
                    "Skipping trigger for '%s' — start time %s is in the past",
                    summary,
                    start_dt.isoformat(),
                )

        _LOGGER.info(
            "Successfully created %d events on '%s' for %s",
            min(len(todos), _EVENT_COUNT),
            calendar_id,
            target_date,
        )

    hass.services.async_register(DOMAIN, "fill_day", fill_day_with_events)

    return True


def _schedule_event_trigger(
    hass: HomeAssistant,
    *,
    start_dt: datetime,
    end_dt: datetime,
    summary: str,
    description: str,
    calendar_id: str,
) -> None:
    """Register an async_track_point_in_time callback for a single event's start."""

    async def on_event_start(fired_at: datetime) -> None:
        """Execute logic when the calendar event start time is reached."""
        event_data = {
            "summary": summary,
            "description": description,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "calendar": calendar_id,
        }

        # 1. Log
        _LOGGER.info(
            "Calendar event started: '%s' (%s → %s)",
            summary,
            start_dt.isoformat(),
            end_dt.isoformat(),
        )

        # 2. Fire a custom HA event — other automations/integrations can subscribe
        hass.bus.async_fire(EVENT_START_FIRED, event_data)

        # 3. Create a persistent notification visible in the HA UI
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"Event started: {summary}",
                "message": (
                    f"{description}\n\n"
                    f"**Start:** {start_dt.strftime('%H:%M')}\n"
                    f"**End:** {end_dt.strftime('%H:%M')}\n"
                    f"**Calendar:** {calendar_id}"
                ),
                "notification_id": f"{DOMAIN}_{start_dt.strftime('%Y%m%d_%H%M')}",
            },
            blocking=False,
        )

    cancel = async_track_point_in_time(hass, on_event_start, start_dt)

    # Store cancel callback so it can be cleaned up on integration unload
    hass.data[DOMAIN]["cancel_listeners"].append(cancel)

    _LOGGER.debug("Scheduled trigger for '%s' at %s", summary, start_dt.isoformat())


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and cancel all scheduled event triggers."""
    hass.services.async_remove(DOMAIN, "fill_day")

    # Cancel every pending point-in-time listener
    for cancel in hass.data[DOMAIN].get("cancel_listeners", []):
        cancel()

    hass.data[DOMAIN]["cancel_listeners"].clear()
    _LOGGER.debug("Unloaded %s and cancelled all event triggers", DOMAIN)

    return True
