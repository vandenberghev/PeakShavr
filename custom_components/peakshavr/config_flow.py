"""Config flow for PeakShavr."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import CONF_MODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .config import resolve_runtime_config
from .const import (
    CONF_ENABLED,
    CONF_ENERGY_MODE,
    CONF_ENERGY_SENSOR,
    CONF_ENERGY_SENSOR_DAY,
    CONF_ENERGY_SENSOR_NIGHT,
    CONF_ESCALATION_INTERVAL_SECONDS,
    CONF_ESCALATION_WINDOW_SECONDS,
    CONF_LOAD_COOLDOWN_S,
    CONF_LOAD_ENTITY_ID,
    CONF_LOAD_EXPECTED_SOURCE_MODE,
    CONF_LOAD_MANUAL_EXPECTED_KW,
    CONF_LOAD_MIN_REQUIRED_KW,
    CONF_LOAD_MIN_ON_TIME_S,
    CONF_LOAD_POWER_SENSOR,
    CONF_LOAD_PRIORITY,
    CONF_NORMAL_INTERVAL_SECONDS,
    CONF_OVERRIDE_BACKOFF_SECONDS,
    CONF_POWER_SENSOR,
    CONF_TARGET_KW,
    CONF_TELEMETRY_CONFLICT_ABS_KW,
    CONF_TELEMETRY_CONFLICT_REL,
    CONF_TELEMETRY_SILENCE_SECONDS,
    DEFAULT_ESCALATION_INTERVAL_SECONDS,
    DEFAULT_ESCALATION_WINDOW_SECONDS,
    DEFAULT_LOAD_COOLDOWN_SECONDS,
    DEFAULT_LOAD_MIN_ON_TIME_SECONDS,
    DEFAULT_NORMAL_INTERVAL_SECONDS,
    DEFAULT_OVERRIDE_BACKOFF_SECONDS,
    DEFAULT_TARGET_KW,
    DEFAULT_TELEMETRY_CONFLICT_ABS_KW,
    DEFAULT_TELEMETRY_CONFLICT_REL,
    DEFAULT_TELEMETRY_SILENCE_SECONDS,
    DOMAIN,
    ENERGY_MODE_SPLIT,
    ENERGY_MODE_TOTAL,
    LOAD_SUPPORTED_DOMAINS,
    NAME,
    SUBENTRY_TYPE_LOAD,
    LOAD_EXPECTED_SOURCE_MANUAL,
    LOAD_EXPECTED_SOURCE_SENSOR,
)
from .load_subentry import format_load_subentry_title
from .models import LoadConfig
from .number_utils import format_optional_kw, parse_localized_float
from .source_fields import normalize_source_fields, source_field_requirements
from .validation import validate_energy_entity_state, validate_power_entity_state

LOAD_MODE_SENSOR = LOAD_EXPECTED_SOURCE_SENSOR
LOAD_MODE_MANUAL = LOAD_EXPECTED_SOURCE_MANUAL


class PeakShavrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for PeakShavr."""

    VERSION = 3

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate_source_input(self.hass, user_input)
            if not errors:
                data = normalize_source_fields(user_input)
                options = {
                    CONF_TARGET_KW: float(user_input[CONF_TARGET_KW]),
                    CONF_ENABLED: True,
                    CONF_TELEMETRY_SILENCE_SECONDS: DEFAULT_TELEMETRY_SILENCE_SECONDS,
                    CONF_TELEMETRY_CONFLICT_ABS_KW: DEFAULT_TELEMETRY_CONFLICT_ABS_KW,
                    CONF_TELEMETRY_CONFLICT_REL: DEFAULT_TELEMETRY_CONFLICT_REL,
                    CONF_OVERRIDE_BACKOFF_SECONDS: DEFAULT_OVERRIDE_BACKOFF_SECONDS,
                    CONF_NORMAL_INTERVAL_SECONDS: DEFAULT_NORMAL_INTERVAL_SECONDS,
                    CONF_ESCALATION_INTERVAL_SECONDS: DEFAULT_ESCALATION_INTERVAL_SECONDS,
                    CONF_ESCALATION_WINDOW_SECONDS: DEFAULT_ESCALATION_WINDOW_SECONDS,
                }
                return self.async_create_entry(title=NAME, data=data, options=options)

        return self.async_show_form(
            step_id="user",
            data_schema=_source_schema(user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry):
        return PeakShavrOptionsFlow(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry types for this integration."""
        return {SUBENTRY_TYPE_LOAD: PeakShavrLoadSubentryFlow}


class PeakShavrOptionsFlow(config_entries.OptionsFlow):
    """Options flow for PeakShavr."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        actions: dict[str, str] = {"global": "Edit global settings"}

        if user_input is not None:
            action = user_input["action"]
            if action == "global":
                return await self.async_step_global()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=label,
                                )
                                for key, label in actions.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_global(self, user_input: dict[str, Any] | None = None):
        runtime = resolve_runtime_config(self._config_entry)
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate_source_input(self.hass, user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data=normalize_source_fields(user_input),
                )
                updated_options = dict(self._config_entry.options)
                updated_options.update(
                    {
                        CONF_TARGET_KW: float(user_input[CONF_TARGET_KW]),
                        CONF_ENABLED: bool(user_input[CONF_ENABLED]),
                        CONF_TELEMETRY_SILENCE_SECONDS: int(
                            user_input[CONF_TELEMETRY_SILENCE_SECONDS]
                        ),
                        CONF_TELEMETRY_CONFLICT_ABS_KW: float(
                            user_input[CONF_TELEMETRY_CONFLICT_ABS_KW]
                        ),
                        CONF_TELEMETRY_CONFLICT_REL: float(
                            user_input[CONF_TELEMETRY_CONFLICT_REL]
                        ),
                        CONF_OVERRIDE_BACKOFF_SECONDS: int(
                            user_input[CONF_OVERRIDE_BACKOFF_SECONDS]
                        ),
                        CONF_NORMAL_INTERVAL_SECONDS: int(
                            user_input[CONF_NORMAL_INTERVAL_SECONDS]
                        ),
                        CONF_ESCALATION_INTERVAL_SECONDS: int(
                            user_input[CONF_ESCALATION_INTERVAL_SECONDS]
                        ),
                        CONF_ESCALATION_WINDOW_SECONDS: int(
                            user_input[CONF_ESCALATION_WINDOW_SECONDS]
                        ),
                    }
                )
                return self.async_create_entry(title="", data=updated_options)

        return self.async_show_form(
            step_id="global",
            data_schema=_source_schema(
                {
                    CONF_POWER_SENSOR: runtime.power_sensor,
                    CONF_ENERGY_MODE: runtime.energy_mode,
                    CONF_ENERGY_SENSOR: runtime.energy_sensor,
                    CONF_ENERGY_SENSOR_DAY: runtime.energy_sensor_day,
                    CONF_ENERGY_SENSOR_NIGHT: runtime.energy_sensor_night,
                    CONF_TARGET_KW: runtime.target_kw,
                    CONF_ENABLED: runtime.enabled,
                    CONF_TELEMETRY_SILENCE_SECONDS: runtime.telemetry_silence_seconds,
                    CONF_TELEMETRY_CONFLICT_ABS_KW: runtime.telemetry_conflict_abs_kw,
                    CONF_TELEMETRY_CONFLICT_REL: runtime.telemetry_conflict_rel,
                    CONF_OVERRIDE_BACKOFF_SECONDS: runtime.override_backoff_seconds,
                    CONF_NORMAL_INTERVAL_SECONDS: runtime.normal_interval_seconds,
                    CONF_ESCALATION_INTERVAL_SECONDS: runtime.escalation_interval_seconds,
                    CONF_ESCALATION_WINDOW_SECONDS: runtime.escalation_window_seconds,
                },
                include_runtime=True,
            ),
            errors=errors,
        )

class PeakShavrLoadSubentryFlow(ConfigSubentryFlow):
    """Config-subentry flow for managed load configuration."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle creating a new managed-load subentry."""
        return await self._async_step_load_editor(user_input=user_input, subentry=None)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguring an existing managed-load subentry."""
        return await self._async_step_load_editor(
            user_input=user_input,
            subentry=self._get_reconfigure_subentry(),
        )

    async def _async_step_load_editor(
        self,
        *,
        user_input: dict[str, Any] | None,
        subentry,
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        existing = LoadConfig.from_mapping(dict(subentry.data)) if subentry else None
        config_entry = self._get_entry()
        if user_input is not None:
            load_mode = user_input[CONF_MODE]
            power_sensor = user_input.get(CONF_LOAD_POWER_SENSOR)
            raw_manual_kw = user_input.get(CONF_LOAD_MANUAL_EXPECTED_KW)
            manual_kw = parse_localized_float(raw_manual_kw)
            min_required_kw = parse_localized_float(user_input.get(CONF_LOAD_MIN_REQUIRED_KW))
            load_entity = user_input[CONF_LOAD_ENTITY_ID]
            load_domain = str(load_entity).split(".", 1)[0]
            if load_domain not in LOAD_SUPPORTED_DOMAINS:
                errors[CONF_LOAD_ENTITY_ID] = "invalid_load_domain"

            existing_entity_subentry = _load_subentry_by_entity(config_entry, load_entity)
            if existing_entity_subentry and (
                subentry is None
                or existing_entity_subentry.subentry_id != subentry.subentry_id
            ):
                errors["base"] = "already_configured"

            persisted_power_sensor = (
                power_sensor
                if power_sensor is not None
                else existing.power_sensor
                if existing
                else None
            )
            manual_kw_supplied = not _is_blank(raw_manual_kw)
            persisted_manual_kw = (
                manual_kw
                if manual_kw_supplied and manual_kw is not None
                else existing.manual_expected_kw
                if existing
                else None
            )

            if load_mode == LOAD_MODE_SENSOR and not persisted_power_sensor:
                errors[CONF_LOAD_POWER_SENSOR] = "required"
            if load_mode == LOAD_MODE_MANUAL and persisted_manual_kw is None:
                errors[CONF_LOAD_MANUAL_EXPECTED_KW] = "required"
            if load_mode == LOAD_MODE_MANUAL and manual_kw_supplied and manual_kw is None:
                errors[CONF_LOAD_MANUAL_EXPECTED_KW] = "manual_kw_invalid"
            if (
                load_mode == LOAD_MODE_MANUAL
                and persisted_manual_kw is not None
                and persisted_manual_kw <= 0
            ):
                errors[CONF_LOAD_MANUAL_EXPECTED_KW] = "manual_kw_invalid"
            if min_required_kw is None:
                errors[CONF_LOAD_MIN_REQUIRED_KW] = "required"
            elif min_required_kw < 0:
                errors[CONF_LOAD_MIN_REQUIRED_KW] = "min_required_kw_invalid"
            if load_mode == LOAD_MODE_SENSOR and persisted_power_sensor:
                power_validation = validate_power_entity_state(
                    self.hass.states.get(persisted_power_sensor)
                )
                if not power_validation.ok:
                    errors[CONF_LOAD_POWER_SENSOR] = (
                        power_validation.error_key or "invalid_sensor"
                    )

            if not errors:
                load_data = {
                    CONF_LOAD_ENTITY_ID: load_entity,
                    CONF_LOAD_PRIORITY: int(user_input[CONF_LOAD_PRIORITY]),
                    CONF_LOAD_POWER_SENSOR: persisted_power_sensor,
                    CONF_LOAD_MANUAL_EXPECTED_KW: persisted_manual_kw,
                    CONF_LOAD_EXPECTED_SOURCE_MODE: load_mode,
                    CONF_LOAD_MIN_REQUIRED_KW: min_required_kw,
                    CONF_LOAD_COOLDOWN_S: int(user_input[CONF_LOAD_COOLDOWN_S]),
                    CONF_LOAD_MIN_ON_TIME_S: int(user_input[CONF_LOAD_MIN_ON_TIME_S]),
                }
                title = _load_subentry_title(
                    self.hass,
                    load_entity,
                    int(user_input[CONF_LOAD_PRIORITY]),
                )
                if subentry is None:
                    return self.async_create_entry(
                        title=title, data=load_data, unique_id=load_entity
                    )
                return self.async_update_and_abort(
                    entry=config_entry,
                    subentry=subentry,
                    data=load_data,
                    title=title,
                    unique_id=load_entity,
                )

        return self.async_show_form(
            step_id="reconfigure" if subentry else "user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=_load_editor_schema(),
                suggested_values=user_input
                if user_input is not None
                else _load_editor_defaults(existing),
            ),
            errors=errors,
        )


def _load_subentry_by_entity(config_entry: ConfigEntry, load_entity_id: str):
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        subentry_load_entity_id = subentry.data.get(CONF_LOAD_ENTITY_ID)
        if isinstance(subentry_load_entity_id, str) and subentry_load_entity_id == load_entity_id:
            return subentry
        if subentry.unique_id == load_entity_id:
            return subentry
    return None


def _load_editor_defaults(existing: LoadConfig | None) -> dict[str, Any]:
    default_mode = (
        LOAD_MODE_SENSOR
        if existing and existing.power_sensor
        else LOAD_MODE_MANUAL
        if existing and existing.manual_expected_kw is not None
        else LOAD_MODE_SENSOR
    )
    return {
        CONF_LOAD_ENTITY_ID: existing.entity_id if existing else None,
        CONF_LOAD_PRIORITY: existing.priority if existing else 100,
        CONF_MODE: existing.expected_source_mode if existing else default_mode,
        CONF_LOAD_POWER_SENSOR: existing.power_sensor if existing else None,
        CONF_LOAD_MANUAL_EXPECTED_KW: (
            format_optional_kw(existing.manual_expected_kw) if existing else None
        ),
        CONF_LOAD_MIN_REQUIRED_KW: (
            format_optional_kw(existing.min_required_kw) if existing else None
        ),
        CONF_LOAD_COOLDOWN_S: (
            existing.cooldown_seconds if existing else DEFAULT_LOAD_COOLDOWN_SECONDS
        ),
        CONF_LOAD_MIN_ON_TIME_S: (
            existing.min_on_time_seconds if existing else DEFAULT_LOAD_MIN_ON_TIME_SECONDS
        ),
    }


def _load_editor_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LOAD_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=list(LOAD_SUPPORTED_DOMAINS))
            ),
            vol.Required(CONF_LOAD_PRIORITY): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=1000,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_MODE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=LOAD_MODE_SENSOR,
                            label="Use load power sensor",
                        ),
                        selector.SelectOptionDict(
                            value=LOAD_MODE_MANUAL,
                            label="Use manual expected kW",
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_LOAD_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN])
            ),
            vol.Optional(CONF_LOAD_MANUAL_EXPECTED_KW): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                )
            ),
            vol.Required(CONF_LOAD_MIN_REQUIRED_KW): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                )
            ),
            vol.Required(CONF_LOAD_COOLDOWN_S): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3600,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_LOAD_MIN_ON_TIME_S): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3600,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _load_subentry_title(
    hass: HomeAssistant, load_entity_id: str, priority: int
) -> str:
    return format_load_subentry_title(priority, _load_display_name(hass, load_entity_id))


def _load_display_name(hass: HomeAssistant, load_entity_id: str) -> str:
    state = hass.states.get(load_entity_id)
    if state is not None and state.name:
        return state.name
    return load_entity_id


def _is_blank(value: object | None) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _source_schema(
    defaults: Mapping[str, Any] | None = None,
    *,
    include_runtime: bool = False,
) -> vol.Schema:
    defaults = defaults or {}
    require_total, require_split_day, require_split_night = source_field_requirements(
        defaults
    )
    energy_sensor_key = _optional_with_default(
        CONF_ENERGY_SENSOR, defaults.get(CONF_ENERGY_SENSOR)
    )
    energy_day_key = _optional_with_default(
        CONF_ENERGY_SENSOR_DAY, defaults.get(CONF_ENERGY_SENSOR_DAY)
    )
    energy_night_key = _optional_with_default(
        CONF_ENERGY_SENSOR_NIGHT, defaults.get(CONF_ENERGY_SENSOR_NIGHT)
    )
    if require_total:
        energy_sensor_key = _required_with_optional_default(
            CONF_ENERGY_SENSOR, defaults.get(CONF_ENERGY_SENSOR)
        )
    if require_split_day:
        energy_day_key = _required_with_optional_default(
            CONF_ENERGY_SENSOR_DAY, defaults.get(CONF_ENERGY_SENSOR_DAY)
        )
    if require_split_night:
        energy_night_key = _required_with_optional_default(
            CONF_ENERGY_SENSOR_NIGHT, defaults.get(CONF_ENERGY_SENSOR_NIGHT)
        )

    schema: dict[Any, Any] = {
        vol.Required(
            CONF_POWER_SENSOR,
            default=defaults.get(CONF_POWER_SENSOR),
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN])),
        vol.Required(
            CONF_ENERGY_MODE,
            default=defaults.get(CONF_ENERGY_MODE, ENERGY_MODE_TOTAL),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=ENERGY_MODE_TOTAL,
                        label="Single cumulative import sensor",
                    ),
                    selector.SelectOptionDict(
                        value=ENERGY_MODE_SPLIT,
                        label="Split day/night cumulative import sensors",
                    ),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        energy_sensor_key: selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN])
        ),
        energy_day_key: selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN])
        ),
        energy_night_key: selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN])
        ),
        vol.Required(
            CONF_TARGET_KW,
            default=defaults.get(CONF_TARGET_KW, DEFAULT_TARGET_KW),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.5,
                max=40,
                step=0.1,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    }

    if include_runtime:
        schema.update(
            {
                vol.Required(
                    CONF_ENABLED,
                    default=defaults.get(CONF_ENABLED, True),
                ): bool,
                vol.Required(
                    CONF_TELEMETRY_SILENCE_SECONDS,
                    default=defaults.get(
                        CONF_TELEMETRY_SILENCE_SECONDS,
                        DEFAULT_TELEMETRY_SILENCE_SECONDS,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10,
                        max=900,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_TELEMETRY_CONFLICT_ABS_KW,
                    default=defaults.get(
                        CONF_TELEMETRY_CONFLICT_ABS_KW,
                        DEFAULT_TELEMETRY_CONFLICT_ABS_KW,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.05,
                        max=5,
                        step=0.05,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_TELEMETRY_CONFLICT_REL,
                    default=defaults.get(
                        CONF_TELEMETRY_CONFLICT_REL,
                        DEFAULT_TELEMETRY_CONFLICT_REL,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.05,
                        max=2,
                        step=0.05,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_OVERRIDE_BACKOFF_SECONDS,
                    default=defaults.get(
                        CONF_OVERRIDE_BACKOFF_SECONDS,
                        DEFAULT_OVERRIDE_BACKOFF_SECONDS,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=3600,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_NORMAL_INTERVAL_SECONDS,
                    default=defaults.get(
                        CONF_NORMAL_INTERVAL_SECONDS,
                        DEFAULT_NORMAL_INTERVAL_SECONDS,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=300,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_ESCALATION_INTERVAL_SECONDS,
                    default=defaults.get(
                        CONF_ESCALATION_INTERVAL_SECONDS,
                        DEFAULT_ESCALATION_INTERVAL_SECONDS,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=60,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_ESCALATION_WINDOW_SECONDS,
                    default=defaults.get(
                        CONF_ESCALATION_WINDOW_SECONDS,
                        DEFAULT_ESCALATION_WINDOW_SECONDS,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=600,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    return vol.Schema(schema)


async def _validate_source_input(
    hass: HomeAssistant, user_input: Mapping[str, Any]
) -> dict[str, str]:
    errors: dict[str, str] = {}

    energy_mode = user_input[CONF_ENERGY_MODE]
    if energy_mode == ENERGY_MODE_TOTAL:
        if not user_input.get(CONF_ENERGY_SENSOR):
            errors[CONF_ENERGY_SENSOR] = "required"
    else:
        if not user_input.get(CONF_ENERGY_SENSOR_DAY):
            errors[CONF_ENERGY_SENSOR_DAY] = "required"
        if not user_input.get(CONF_ENERGY_SENSOR_NIGHT):
            errors[CONF_ENERGY_SENSOR_NIGHT] = "required"

    power_state = hass.states.get(user_input[CONF_POWER_SENSOR])
    power_validation = validate_power_entity_state(power_state)
    if not power_validation.ok:
        errors[CONF_POWER_SENSOR] = power_validation.error_key or "invalid_sensor"

    energy_entities = (
        [user_input[CONF_ENERGY_SENSOR]]
        if energy_mode == ENERGY_MODE_TOTAL
        else [user_input.get(CONF_ENERGY_SENSOR_DAY), user_input.get(CONF_ENERGY_SENSOR_NIGHT)]
    )
    for entity_id in energy_entities:
        if not entity_id:
            continue
        energy_state = hass.states.get(entity_id)
        energy_validation = validate_energy_entity_state(energy_state)
        if not energy_validation.ok:
            field = (
                CONF_ENERGY_SENSOR
                if energy_mode == ENERGY_MODE_TOTAL
                else CONF_ENERGY_SENSOR_DAY
                if entity_id == user_input.get(CONF_ENERGY_SENSOR_DAY)
                else CONF_ENERGY_SENSOR_NIGHT
            )
            errors[field] = energy_validation.error_key or "invalid_sensor"

    return errors


def _optional_with_default(field: str, default: Any) -> Any:
    if default is None:
        return vol.Optional(field)
    return vol.Optional(field, default=default)


def _required_with_optional_default(field: str, default: Any) -> Any:
    if default is None:
        return vol.Required(field)
    return vol.Required(field, default=default)
