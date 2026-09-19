from __future__ import annotations

import hashlib
import json
from typing import Any


class FlightStateTransformer:
    """
    Transforms parsed MACS FlightState rows into clean,
    database-ready Python dictionaries.

    This class does not connect to PostgreSQL.
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
        "X": "x",
        "Y": "y",
        "ALT": "altitude_ft",
        "IAS": "indicated_airspeed",
        "MACH": "mach",
        "VS": "vertical_speed",
        "GS": "ground_speed",
        "TAS": "true_airspeed",
        "BANK": "bank_angle",
        "ALT_T": "target_altitude_ft",
        "HDG_T": "target_heading",
        "SPD_T": "target_speed",
        "WD": "wind_direction",
        "WS": "wind_speed",
        "THRUSTPERCENT": "thrust_percent",
        "DISPLAYED_DELAY": "displayed_delay",
        "DELAY": "delay",
        "FLAPS": "flaps",
        "GEAR": "gear",
        "FLIGHT_PHASE": "flight_phase",
        "THRUST": "thrust",
    }

    FLOAT_FIELDS = {
        "WEIGHT",
        "FUEL_RATE",
        "REL_TIME",
        "LAT",
        "LONG",
        "X",
        "Y",
        "ALT",
        "IAS",
        "MACH",
        "VS",
        "GS",
        "TAS",
        "BANK",
        "ALT_T",
        "HDG_T",
        "SPD_T",
        "WD",
        "WS",
        "THRUSTPERCENT",
        "DISPLAYED_DELAY",
        "DELAY",
        "THRUST",
    }

    INTEGER_FIELDS = {
        "PROC",
        "CID",
        "SIM_TIME",
    }

    def transform_row(
        self,
        row: dict[str, Any],
        source_line_number: int | None = None,
    ) -> dict[str, Any]:
        """
        Transform one parsed FlightState row.
        """

        transformed = {}

        for source_field, database_field in self.FIELD_MAP.items():
            value = row.get(source_field)

            if source_field in self.FLOAT_FIELDS:
                value = self._to_float(value)

            elif source_field in self.INTEGER_FIELDS:
                value = self._to_int(value)

            else:
                value = self._clean_string(value)

            transformed[database_field] = value

        transformed["source_line_number"] = source_line_number
        transformed["record_hash"] = self._create_record_hash(row)

        return transformed

    def transform_rows(
        self,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Transform all FlightState rows.
        """

        transformed_rows = []

        for row_number, row in enumerate(rows, start=1):
            transformed_row = self.transform_row(
                row=row,
                source_line_number=row_number,
            )

            transformed_rows.append(transformed_row)

        return transformed_rows

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        return value

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _create_record_hash(row: dict[str, Any]) -> str:
        """
        Create a repeatable SHA-256 hash from the original parsed row.

        Later this helps us detect duplicate records during database loading.
        """

        serialized_row = json.dumps(
            row,
            sort_keys=True,
            default=str,
        )

        return hashlib.sha256(
            serialized_row.encode("utf-8")
        ).hexdigest()
