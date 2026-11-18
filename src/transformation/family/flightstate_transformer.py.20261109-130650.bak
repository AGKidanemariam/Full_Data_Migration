"""Normalize parsed MACS FlightState records for the deployed v3 schema.

This is a transformer, not a log-file parser or database loader. Input rows
use original, case-sensitive MACS headers and JSON-compatible values. The
parser must retain physical source-line numbers. The loader still supplies
an authoritative UTC time, simulation_run_id and source_file_id.
See FlightState_Review.md for migration notes and unresolved source semantics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Iterator, Mapping
from datetime import time
from decimal import Decimal, InvalidOperation
from typing import Any

__version__ = "2.0.0"


class FlightStateValidationError(ValueError):
    """A record cannot be normalized without hiding or changing invalid data."""

    def __init__(self, field: str, line_number: int | None, reason: str):
        self.field = field
        self.source_line_number = line_number
        location = f"source line {line_number}" if line_number else "unknown source line"
        super().__init__(f"FlightState {location}, {field}: {reason}")


class FlightStateTransformer:
    """Return validated dictionaries whose keys match actual v3 columns.

    longitude_convention must explicitly be east_positive or west_positive
    when LONG is present. Output longitude is always east-positive. Never
    select a convention from the sign or apparent geography of a single row.

    missing_values declares field-specific tokens, for example
    {"WEIGHT": ["-999999", "-999999.0"]}. Only None, blank, null and _NOT_SET_
    are missing by default. All original values remain in raw_fields.

    DISPLAYED_DELAY and DELAY are retained only in raw_fields until their
    units/format are confirmed for the *_ms columns. Other unmapped fields,
    including FP_* fields, are also retained there unchanged. IS_OVER_FLT is
    not assumed to mean the schema's is_overflow_flight without a definition.
    """

    FIELD_MAP = {
        "UTC_TIME": "utc_time",
        "WEIGHT": "weight_lbs",
        "FUEL_RATE": "fuel_rate_lb_per_hr",
        "REL_TIME": "relative_time_sec",
        "LOG_TIME": "log_time",
        "PROC": "processor_id",
        "CALLSIGN": "callsign",
        "CID": "cid",
        "FLIGHT_RULES": "flight_rules",
        "STAMP_TIME": "stamp_time",
        "SIM_TIME": "sim_time_ms",
        "LAT": "latitude",
        "LONG": "longitude",
        "X": "x_coord_nm",
        "Y": "y_coord_nm",
        "ALT": "altitude_ft",
        "IAS": "indicated_airspeed_knots",
        "MACH": "mach_number",
        "TH": "true_heading_deg",
        "TGT": "target_value_raw",
        "VS": "vertical_speed_ft_per_min",
        "GS": "ground_speed_knots",
        "TAS": "true_airspeed_knots",
        "MH": "magnetic_heading_deg",
        "BANK": "bank_angle_deg",
        "ALT_T": "altitude_target_ft",
        "HDG_T": "heading_target_deg",
        "SPD_T": "speed_target_knots",
        "CTE": "cross_track_error",
        "FPE": "flight_path_error",
        "WD": "wind_direction_deg",
        "WS": "wind_speed_knots",
        "THRUSTPERCENT": "thrust_percent",
        "ATC": "atc_code",
        "GEO": "geo_sector",
        "IS_ARR": "is_arrival",
        "IS_DEP": "is_departure",
        "FLAPS": "flaps_position",
        "GEAR": "gear_position",
        "FLIGHT_PHASE": "flight_phase",
        "THRUST": "thrust_state",
        "FuncAlloc-IH-AH-AFC-IATAC-DC-RSC-USR-RUC-UUR-RTFAT-RWC-UWR": "func_alloc_state",
        "DATABLOCK_MODE": "datablock_mode",
        "IN_VNAV": "vnav_active",
        "IN_LNAV": "lnav_active",
        "IN_AUTO_SPD": "auto_speed_active",
        "IN_SPACE_SPD": "space_speed_active",
        "IN_MACH": "mach_active",
    }
    FLOAT_FIELDS = frozenset({
        "WEIGHT", "FUEL_RATE", "REL_TIME", "LAT", "LONG", "X", "Y", "ALT",
        "IAS", "MACH", "TH", "TGT", "VS", "GS", "TAS", "MH", "BANK",
        "ALT_T", "HDG_T", "SPD_T", "CTE", "FPE", "WD", "WS",
        "THRUSTPERCENT", "FLAPS",
    })
    INTEGER_FIELDS = frozenset({"PROC", "CID", "SIM_TIME"})
    BOOLEAN_FIELDS = frozenset({
        "IS_ARR", "IS_DEP", "IN_VNAV", "IN_LNAV",
        "IN_AUTO_SPD", "IN_SPACE_SPD", "IN_MACH",
    })
    TIME_FIELDS = frozenset({"UTC_TIME", "LOG_TIME", "STAMP_TIME"})
    RAW_ONLY_FIELDS = frozenset({"DISPLAYED_DELAY", "DELAY", "IS_OVER_FLT"})
    _POSITION_KEYS = frozenset({"source_line_number", "source_record_index"})
    _MISSING_TOKENS = frozenset({"", "null", "_not_set_"})
    _INT32 = (-(2**31), 2**31 - 1)
    _INT64 = (-(2**63), 2**63 - 1)
    _CLOCK = re.compile(r"\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\Z")

    def __init__(
        self,
        *,
        longitude_convention: str | None = None,
        missing_values: Mapping[str, Iterable[str]] | None = None,
    ):
        if longitude_convention not in (None, "east_positive", "west_positive"):
            raise ValueError("longitude_convention must be east_positive or west_positive")
        self.longitude_convention = longitude_convention
        self.missing_values: dict[str, frozenset[str]] = {}
        for field, tokens in (missing_values or {}).items():
            if field not in self.FIELD_MAP:
                raise ValueError(f"Missing-value policy names an unmapped field: {field}")
            if isinstance(tokens, (str, bytes)):
                raise TypeError("Each missing-value policy must be an iterable of strings")
            normalized = []
            for token in tokens:
                if not isinstance(token, str):
                    raise TypeError("Missing-value tokens must be strings")
                normalized.append(token.strip().casefold())
            self.missing_values[field] = frozenset(normalized)

    def transform_row(
        self,
        row: Mapping[str, Any],
        source_line_number: int | None = None,
        *,
        source_record_index: int | None = None,
    ) -> dict[str, Any]:
        """Normalize one row using its physical source line, never its list index.

        Position comes from arguments or lower-case metadata keys in row.
        Conflicts are errors. source_record_index defaults to 1; the parser
        must supply a deterministic ordinal when expanding one physical line.
        Invalid values raise FlightStateValidationError instead of becoming NULL.
        """
        if not isinstance(row, Mapping):
            raise TypeError("row must map MACS field names to parsed values")
        line = self._position(row, "source_line_number", source_line_number, None)
        ordinal = self._position(row, "source_record_index", source_record_index, line)
        original = {key: value for key, value in row.items() if key not in self._POSITION_KEYS}
        try:
            self._check_json_value(original)
            # Preserve legacy hash bytes for supported raw JSON rows. Unsupported
            # objects are rejected rather than silently changed with default=str.
            serialized = json.dumps(original, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
            raise FlightStateValidationError("raw_fields", line, str(exc)) from exc

        transformed: dict[str, Any] = {}
        for source, target in self.FIELD_MAP.items():
            value = row.get(source)
            if self._is_missing(source, value):
                converted = None
            else:
                try:
                    if source in self.FLOAT_FIELDS:
                        converted = self._to_float(value)
                    elif source in self.INTEGER_FIELDS:
                        bounds = self._INT64 if source == "SIM_TIME" else self._INT32
                        converted = self._to_int(value, bounds)
                    elif source in self.BOOLEAN_FIELDS:
                        converted = self._to_bool(value)
                    elif source in self.TIME_FIELDS:
                        converted = self._to_time(value)
                    else:
                        converted = self._clean_string(value)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise FlightStateValidationError(source, line, str(exc)) from exc
            transformed[target] = converted

        if transformed["callsign"] is None:
            raise FlightStateValidationError("CALLSIGN", line, "a nonempty callsign is required")
        for field, target, low, high in (
            ("LAT", "latitude", -90, 90), ("LONG", "longitude", -180, 180)
        ):
            value = transformed[target]
            if value is not None and not low <= value <= high:
                raise FlightStateValidationError(field, line, f"must be between {low} and {high}")
        if transformed["longitude"] is not None:
            if self.longitude_convention is None:
                raise FlightStateValidationError(
                    "LONG", line, "confirm longitude_convention: east_positive or west_positive"
                )
            if self.longitude_convention == "west_positive":
                transformed["longitude"] = -transformed["longitude"]

        transformed["source_line_number"] = line
        transformed["source_record_index"] = ordinal
        transformed["record_hash"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        # Independent snapshot retains every source field and its JSON type,
        # including fields not mapped into typed database columns.
        transformed["raw_fields"] = json.loads(serialized)
        return transformed

    def transform_rows(self, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Return all transformed rows; each row must carry source_line_number."""
        return list(self.iter_transform_rows(rows))

    def iter_transform_rows(self, rows: Iterable[Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
        """Transform lazily for large files; fail on the first invalid row."""
        for row in rows:
            yield self.transform_row(row)

    def _is_missing(self, field: str, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            token = str(value).strip().casefold()
            return token in self._MISSING_TOKENS or token in self.missing_values.get(field, ())
        return False

    @classmethod
    def _position(cls, row: Mapping[str, Any], key: str, explicit: Any, line: int | None) -> int:
        embedded = row.get(key)
        supplied = explicit if explicit is not None else embedded
        if supplied is None and key == "source_record_index":
            return 1
        if supplied is None:
            raise FlightStateValidationError(key, line, "the parser must supply the physical source line")
        bounds = (1, cls._INT64[1] if key == "source_line_number" else cls._INT32[1])
        try:
            result = cls._to_int(supplied, bounds)
            if explicit is not None and embedded is not None:
                if result != cls._to_int(embedded, bounds):
                    raise ValueError("argument conflicts with row metadata")
            return result
        except (TypeError, ValueError, OverflowError) as exc:
            raise FlightStateValidationError(key, line, str(exc)) from exc

    @staticmethod
    def _clean_string(value: Any) -> str:
        if not isinstance(value, (str, int, float, bool)):
            raise TypeError("expected a scalar string or number")
        return str(value).strip()

    @staticmethod
    def _to_float(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise TypeError("expected a numeric value, not a boolean or object")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("NaN, infinity and numeric overflow are not valid telemetry")
        if result == 0:
            try:
                nonzero = Decimal(str(value).strip()) != 0
            except InvalidOperation as exc:
                raise ValueError("invalid number") from exc
            if nonzero:
                raise ValueError("numeric underflow would silently turn the value into zero")
        return result

    @staticmethod
    def _to_int(value: Any, bounds: tuple[int, int] = (-(2**63), 2**63 - 1)) -> int:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise TypeError("expected an exact integer, not a boolean or object")
        if isinstance(value, float) and abs(value) >= 2**53:
            raise ValueError("large integers must arrive as strings or integers, not lossy floats")
        try:
            number = Decimal(str(value).strip())
        except InvalidOperation as exc:
            raise ValueError("invalid integer") from exc
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("expected a finite whole number; fractional values are not truncated")
        if not bounds[0] <= number <= bounds[1]:
            raise ValueError(f"integer is outside {bounds[0]}..{bounds[1]}")
        return int(number)

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            token = value.strip().casefold()
            if token in ("true", "1"):
                return True
            if token in ("false", "0"):
                return False
        raise ValueError("expected true/false or 1/0")

    @classmethod
    def _to_time(cls, value: Any) -> str:
        if not isinstance(value, str) or not cls._CLOCK.fullmatch(value.strip()):
            raise ValueError("expected HH:MM:SS with optional fractional seconds, without timezone")
        cleaned = value.strip()
        time.fromisoformat(cleaned)
        return cleaned

    @classmethod
    def _check_json_value(cls, value: Any) -> None:
        """Reject values JSONB cannot faithfully hold; never stringify objects."""
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("PostgreSQL JSONB/text cannot store a NUL character")
            value.encode("utf-8")
        elif value is None or isinstance(value, (bool, int)):
            return
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("raw numeric NaN/infinity is not valid JSON; preserve its source token")
        elif isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise TypeError("raw JSON object keys must be strings")
                cls._check_json_value(key)
                cls._check_json_value(child)
        elif isinstance(value, list):
            for child in value:
                cls._check_json_value(child)
        else:
            raise TypeError(f"unsupported raw JSON value type: {type(value).__name__}")
