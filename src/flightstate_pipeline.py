"""FlightState staging and PostgreSQL loading for the reviewed MACS v3 schema."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import (
    MetaData,
    Table,
    bindparam,
    create_engine,
    func,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


VERSION = "3.2.0"
ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc

PARSER_PATH = (
    ROOT / "data-migration/src/data_migration/macs_parser/core.py"
)
TRANSFORMER_PATH = (
    ROOT / "src/transformation/family/flightstate_transformer.py"
)

SCHEMA_MARKERS = {
    "relational":
        "121f9084ae71f98d099897ba0f809064118386eabcb037195549209167d0f4eb",
    "timeseries":
        "ad88c805caed69bb329e70385c7b8afb15a27ed546a67862cd2a1931c4a73310",
}

REQUIRED_HEADERS = {"UTC_TIME", "CALLSIGN", "SIM_TIME", "LAT", "LONG"}
METADATA_KEY = "flightstate_pipeline"
_COMPONENTS = None

# A trailing ! means NOT NULL.
# These layouts come from the supplied v3 schema contracts.
LAYOUT = {
    "pipeline_runs": {
        "bigint!": "pipeline_run_id records_written",
        "uuid!": "run_uuid",
        "text!": "trigger_type status",
        "text": "host_name code_version message",
        "integer": "process_id",
        "timestamp with time zone!": "started_at",
        "timestamp with time zone": "finished_at",
        "integer!": "files_seen files_succeeded files_failed",
        "jsonb!": "details",
    },
    "simulation_runs": {
        "bigint!": "simulation_run_id",
        "text!": "run_key source_timezone",
        "integer": "run_number",
        "date!": "experiment_date",
        "text": (
            "experiment_condition scenario_file_path scenario_name macs_version "
            "fep_url fep_version schema_file uss_url notes"
        ),
        "timestamp with time zone": "started_at ended_at",
        "timestamp with time zone!": "created_at updated_at",
    },
    "source_files": {
        "bigint!": "source_file_id rejected_records loaded_records",
        "bigint": (
            "simulation_run_id file_size_bytes total_lines parsed_records"
        ),
        "text!": "sha256 file_name processing_status",
        "text": (
            "original_path extracted_path file_family file_extension "
            "schema_signature encoding delimiter first_error"
        ),
        "timestamp with time zone!": "discovered_at created_at updated_at",
        "timestamp with time zone": (
            "extracted_at parsed_at validated_at transformed_at loaded_at"
        ),
        "jsonb!": "metadata",
    },
    "processing_events": {
        "bigint!": (
            "processing_event_id records_read records_written records_rejected"
        ),
        "bigint": "pipeline_run_id source_file_id duration_ms",
        "text!": "stage status",
        "timestamp with time zone!": "started_at",
        "timestamp with time zone": "finished_at",
        "text": "message",
        "jsonb!": "details",
    },
    "validation_results": {
        "bigint!": "validation_result_id source_file_id",
        "bigint": "pipeline_run_id source_row_number",
        "text!": "rule_name severity message",
        "boolean!": "passed",
        "text": (
            "section_name field_name expected_value actual_value"
        ),
        "timestamp with time zone!": "created_at",
    },
    "source_schema_registry": {
        "bigint!": "source_schema_id",
        "text!": "file_family section_name schema_signature",
        "jsonb!": "column_names",
        "integer!": "column_count",
        "timestamp with time zone!": "first_seen_at last_seen_at",
        "bigint": "first_source_file_id",
        "boolean!": "is_approved",
        "text": "notes",
    },
    "aircraft": {
        "bigint!": "aircraft_id simulation_run_id",
        "text!": "callsign",
        "text": (
            "aircraft_type owner flight_rules beacon_code equipment_avail "
            "free_flight_status"
        ),
        "boolean": (
            "dlnk_equipped rta_capable cpdlc_capable self_spacing_capable"
        ),
        "timestamp with time zone": "first_seen_at last_seen_at",
        "timestamp with time zone!": "created_at updated_at",
    },
    "flight_state_telemetry": {
        "timestamp with time zone!": "time loaded_at",
        "bigint!": (
            "simulation_run_id source_file_id source_line_number"
        ),
        "text": (
            "record_hash flight_rules atc_code geo_sector gear_position "
            "flight_phase thrust_state func_alloc_state datablock_mode "
            "eta_to_destination_raw utm_state fp_type fp_gate_name fp_mfix_name "
            "fp_ofix_name fp_route fp_depart_fix fp_coord_frd fp_coord_fix "
            "fp_dest_fix fp_dest_name fp_rw_name fp_config fp_beacon fp_atc_type "
            "fp_data_src fp_equip_avail"
        ),
        "bigint": (
            "aircraft_id sim_time_ms fp_depart_time_ms fp_time_enroute_sec "
            "fp_faa_coord_time_ms fp_coord_time_ms fp_time_rcd_ms"
        ),
        "time(3) without time zone": "utc_time log_time stamp_time",
        "double precision": (
            "relative_time_sec latitude longitude x_coord_nm y_coord_nm "
            "altitude_ft indicated_airspeed_knots mach_number true_heading_deg "
            "target_value_raw vertical_speed_ft_per_min ground_speed_knots "
            "true_airspeed_knots magnetic_heading_deg bank_angle_deg weight_lbs "
            "fuel_rate_lb_per_hr altitude_target_ft heading_target_deg "
            "speed_target_knots cross_track_error flight_path_error "
            "wind_direction_deg wind_speed_knots thrust_percent flaps_position "
            "xy_distance_flown_nm time_flown_sec vertical_distance_flown_ft "
            "xy_along_track_to_dest_nm fp_assign_alt_ft fp_filed_speed_knots "
            "fp_appr_speed_knots fp_land_speed_knots fp_coord_x fp_coord_y"
        ),
        "integer": (
            "processor_id cid displayed_delay_ms delay_ms fp_category "
            "fp_status fp_dlnk_equipd_raw"
        ),
        "text!": "callsign",
        "boolean": (
            "is_overflow_flight is_arrival is_departure vnav_active lnav_active "
            "auto_speed_active space_speed_active mach_active"
        ),
        "integer!": "source_record_index",
        "jsonb!": "raw_fields",
    },
}

PRIMARY_KEYS = {
    "pipeline_runs": ["pipeline_run_id"],
    "simulation_runs": ["simulation_run_id"],
    "source_files": ["source_file_id"],
    "processing_events": ["processing_event_id"],
    "validation_results": ["validation_result_id"],
    "source_schema_registry": ["source_schema_id"],
    "aircraft": ["aircraft_id"],
    "flight_state_telemetry": [
        "time", "source_file_id", "source_line_number", "source_record_index"
    ],
}

UNIQUE_KEYS = {
    "pipeline_runs": [("run_uuid",)],
    "simulation_runs": [("run_key",)],
    "source_files": [
        ("sha256",),
        ("source_file_id", "simulation_run_id"),
    ],
    "source_schema_registry": [
        ("file_family", "section_name", "schema_signature")
    ],
    "aircraft": [
        ("simulation_run_id", "callsign"),
        ("aircraft_id", "simulation_run_id"),
        ("aircraft_id", "simulation_run_id", "callsign"),
    ],
}

# table, local columns, referenced table, referenced columns, ON DELETE
FOREIGN_KEYS = [
    (
        "source_files", ("simulation_run_id",),
        "simulation_runs", ("simulation_run_id",), "RESTRICT"
    ),
    (
        "processing_events", ("pipeline_run_id",),
        "pipeline_runs", ("pipeline_run_id",), "RESTRICT"
    ),
    (
        "processing_events", ("source_file_id",),
        "source_files", ("source_file_id",), "RESTRICT"
    ),
    (
        "validation_results", ("pipeline_run_id",),
        "pipeline_runs", ("pipeline_run_id",), "RESTRICT"
    ),
    (
        "validation_results", ("source_file_id",),
        "source_files", ("source_file_id",), "RESTRICT"
    ),
    (
        "source_schema_registry", ("first_source_file_id",),
        "source_files", ("source_file_id",), "NO ACTION"
    ),
    (
        "aircraft", ("simulation_run_id",),
        "simulation_runs", ("simulation_run_id",), "RESTRICT"
    ),
    (
        "flight_state_telemetry", ("simulation_run_id",),
        "simulation_runs", ("simulation_run_id",), "RESTRICT"
    ),
    (
        "flight_state_telemetry", ("source_file_id", "simulation_run_id"),
        "source_files", ("source_file_id", "simulation_run_id"), "RESTRICT"
    ),
    (
        "flight_state_telemetry",
        ("aircraft_id", "simulation_run_id", "callsign"),
        "aircraft",
        ("aircraft_id", "simulation_run_id", "callsign"),
        "RESTRICT"
    ),
]

CHECK_NAMES = {
    "pipeline_runs": (
        "ck_pipeline_runs_counts ck_pipeline_runs_finish "
        "ck_pipeline_runs_details"
    ),
    "simulation_runs": (
        "ck_simulation_runs_time_order ck_simulation_runs_run_key"
    ),
    "source_files": (
        "ck_source_files_counts ck_source_files_sha256 "
        "ck_source_files_file_name ck_source_files_schema_signature "
        "ck_source_files_metadata"
    ),
    "processing_events": (
        "ck_processing_events_counts ck_processing_events_finish "
        "ck_processing_events_details"
    ),
    "validation_results": "ck_validation_results_row",
    "source_schema_registry": (
        "ck_schema_registry_columns ck_schema_registry_seen_order "
        "ck_source_schema_registry_schema_signature"
    ),
    "aircraft": "ck_aircraft_seen_order ck_aircraft_callsign",
    "flight_state_telemetry": (
        "chk_fst_lat chk_fst_lon "
        "ck_flight_state_telemetry_record_position "
        "ck_flight_state_telemetry_time_finite "
        "ck_flight_state_telemetry_aircraft_callsign "
        "ck_flight_state_telemetry_record_hash "
        "ck_flight_state_telemetry_callsign "
        "ck_flight_state_telemetry_raw_fields"
    ),
}

UPDATE_TABLES = {
    "pipeline_runs", "simulation_runs", "source_files",
    "source_schema_registry", "aircraft",
}


class PipelineError(ValueError):
    pass


def now():
    return datetime.now(UTC)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False
    )


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise PipelineError(f"Duplicate JSON key: {key}")
            result[key] = item
        return result

    def invalid(token):
        raise PipelineError(f"Invalid non-finite JSON number: {token}")

    return json.loads(
        value, object_pairs_hook=pairs, parse_constant=invalid
    )


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def paths():
    load_dotenv(ROOT / ".env", override=False)
    data = ROOT / os.getenv("DATA_FOLDER", "data")
    return {
        "staged": data / os.getenv("STAGED_FOLDER", "staged") / "flightstate",
        "processed": (
            data / os.getenv("PROCESSED_FOLDER", "processed") / "flightstate"
        ),
        "metadata": (
            ROOT / os.getenv("METADATA_FOLDER", "metadata") / "pipeline_v3"
        ),
    }


def load_component(name, path):
    if not path.is_file():
        raise PipelineError(f"Required component does not exist: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PipelineError(f"Cannot load component: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def components():
    global _COMPONENTS
    if _COMPONENTS is None:
        parser = load_component("_macs_pipeline_parser", PARSER_PATH)
        transformer = load_component(
            "_macs_pipeline_transformer", TRANSFORMER_PATH
        )
        for name, module in (
            ("parser", parser), ("transformer", transformer)
        ):
            if getattr(module, "__version__", None) != "2.0.0":
                raise PipelineError(
                    f"The {name} must be the reviewed version 2.0.0."
                )
        descriptor = {
            "pipeline_version": VERSION,
            "pipeline_sha256": sha256_file(Path(__file__)),
            "parser_version": parser.__version__,
            "parser_sha256": sha256_file(PARSER_PATH),
            "transformer_version": transformer.__version__,
            "transformer_sha256": sha256_file(TRANSFORMER_PATH),
        }
        _COMPONENTS = (
            parser.MacsParser,
            transformer.FlightStateTransformer,
            descriptor,
        )
    return _COMPONENTS


def exact_date(value, name):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", value
    ):
        raise PipelineError(f"{name} must use YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PipelineError(f"{name} is not a valid date.") from exc


def utc_datetime(value):
    if not isinstance(value, str) or "T" not in value:
        raise PipelineError("Timestamp requires a date, T, and UTC offset.")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise PipelineError("Timestamp requires an explicit UTC offset.")
    return result.astimezone(UTC)


def validate_config(value):
    if not isinstance(value, dict):
        raise PipelineError("Run configuration must be a JSON object.")
    required = {
        "config_version", "run_key", "experiment_date",
        "source_timezone", "longitude_convention", "time_policy",
    }
    optional = {
        "missing_values", "experiment_condition", "scenario_name", "notes"
    }
    if required - value.keys() or value.keys() - required - optional:
        raise PipelineError(
            f"Configuration keys: missing={sorted(required - value.keys())}; "
            f"unknown={sorted(value.keys() - required - optional)}"
        )
    cfg = parse_json(canonical(value))
    if type(cfg["config_version"]) is not int or cfg["config_version"] != 1:
        raise PipelineError("config_version must be 1.")
    if (
        not isinstance(cfg["run_key"], str)
        or not cfg["run_key"].strip()
        or "\x00" in cfg["run_key"]
    ):
        raise PipelineError("run_key must be nonempty text without NUL.")
    cfg["run_key"] = cfg["run_key"].strip()
    if cfg["run_key"].startswith("REPLACE_"):
        raise PipelineError("Replace the example run_key.")
    exact_date(cfg["experiment_date"], "experiment_date")
    if cfg["source_timezone"] != "UTC":
        raise PipelineError("This implementation requires UTC source clocks.")
    if cfg["longitude_convention"] not in (
        "east_positive", "west_positive"
    ):
        raise PipelineError("Confirm the source longitude convention.")

    policy = cfg["time_policy"]
    if not isinstance(policy, dict):
        raise PipelineError("time_policy must be an object.")
    if policy.get("mode") == "utc_clock":
        if set(policy) != {"mode", "utc_date", "midnight_rollover"}:
            raise PipelineError(
                "utc_clock needs mode, utc_date, and midnight_rollover."
            )
        exact_date(policy["utc_date"], "time_policy.utc_date")
        if policy["midnight_rollover"] not in (
            "reject", "advance_at_midnight"
        ):
            raise PipelineError("Invalid midnight_rollover policy.")
    elif policy.get("mode") == "simulation_elapsed_ms":
        if set(policy) != {"mode", "simulation_start_utc"}:
            raise PipelineError(
                "simulation_elapsed_ms needs mode and simulation_start_utc."
            )
        policy["simulation_start_utc"] = utc_datetime(
            policy["simulation_start_utc"]
        ).isoformat()
    else:
        raise PipelineError("Unsupported time_policy.mode.")

    for key in ("experiment_condition", "scenario_name", "notes"):
        item = cfg.get(key)
        if item is not None and (
            not isinstance(item, str) or "\x00" in item
        ):
            raise PipelineError(f"{key} must be text or null.")

    cfg.setdefault("missing_values", {})
    if not isinstance(cfg["missing_values"], dict):
        raise PipelineError("missing_values must be an object.")
    for tokens in cfg["missing_values"].values():
        if not isinstance(tokens, list) or not all(
            isinstance(token, str) for token in tokens
        ):
            raise PipelineError("Missing-value tokens must be lists of text.")
    _, transformer, _ = components()
    transformer(
        longitude_convention=cfg["longitude_convention"],
        missing_values=cfg["missing_values"],
    )
    return cfg


class Clock:
    def __init__(self, cfg):
        self.policy = cfg["time_policy"]
        self.previous = None
        self.day = (
            exact_date(self.policy["utc_date"], "utc_date")
            if self.policy["mode"] == "utc_clock" else None
        )

    def resolve(self, row):
        if self.policy["mode"] == "simulation_elapsed_ms":
            elapsed = row.get("sim_time_ms")
            if type(elapsed) is not int or elapsed < 0:
                raise PipelineError(
                    "SIM_TIME must be nonnegative integer milliseconds."
                )
            result = utc_datetime(
                self.policy["simulation_start_utc"]
            ) + timedelta(milliseconds=elapsed)
        else:
            if row.get("utc_time") is None:
                raise PipelineError("UTC_TIME is required for utc_clock.")
            clock = time.fromisoformat(row["utc_time"])
            result = datetime.combine(self.day, clock, UTC)
            if self.previous is not None and result < self.previous:
                if (
                    self.policy["midnight_rollover"] == "advance_at_midnight"
                    and self.previous - result >= timedelta(hours=12)
                ):
                    self.day += timedelta(days=1)
                    result = datetime.combine(self.day, clock, UTC)
                else:
                    raise PipelineError(
                        "UTC_TIME moved backwards; verify ordering and policy."
                    )
        if self.previous is not None and result < self.previous:
            raise PipelineError("Canonical timestamps moved backwards.")
        self.previous = result
        return result


def check_precision(row):
    for name in ("utc_time", "log_time", "stamp_time"):
        if row.get(name) is not None:
            if time.fromisoformat(row[name]).microsecond % 1000:
                raise PipelineError(
                    f"{name} exceeds the database TIME(3) precision."
                )


def semantics(cfg, encoding):
    return fingerprint({
        "components": components()[2],
        "run_config": cfg,
        "encoding": encoding,
    })


def bundle_directory(path):
    path = Path(path).resolve()
    return path.parent if path.name == "manifest.json" else path


def verified_rows(path, manifest):
    directory = bundle_directory(path)
    cfg = manifest["run_config"]
    _, transformer_class, _ = components()
    transformer = transformer_class(
        longitude_convention=cfg["longitude_convention"],
        missing_values=cfg["missing_values"],
    )
    clock = Clock(cfg)
    digest = hashlib.sha256()
    count = 0
    previous = None
    first = last = None
    schemas = [
        frozenset(item["column_names"]) for item in manifest["schemas"]
    ]

    with (directory / "records.jsonl").open("rb") as stream:
        for encoded in stream:
            digest.update(encoded)
            row = parse_json(encoded)
            if not isinstance(row, dict):
                raise PipelineError("A staged record is not an object.")
            if frozenset(row["raw_fields"]) not in schemas:
                raise PipelineError("Raw fields do not match an observed schema.")
            expected = transformer.transform_row(
                row["raw_fields"],
                row["source_line_number"],
                source_record_index=row["source_record_index"],
            )
            check_precision(expected)
            timestamp = clock.resolve(expected)
            expected["time"] = timestamp.isoformat()
            if canonical(expected) != canonical(row):
                raise PipelineError(
                    "Staged values differ from raw fields or clock policy."
                )
            position = (
                expected["source_line_number"],
                expected["source_record_index"],
            )
            if previous is not None and position <= previous:
                raise PipelineError("Source positions are not unique and ordered.")
            if position[0] > manifest["parser_report"]["physical_lines"]:
                raise PipelineError("Source position exceeds file length.")
            previous = position
            count += 1
            first = first or timestamp.isoformat()
            last = timestamp.isoformat()
            row["time"] = timestamp
            yield row

    if (
        digest.hexdigest() != manifest["records_sha256"]
        or count != manifest["records"]
        or first != manifest["time_min"]
        or last != manifest["time_max"]
    ):
        raise PipelineError("Staged checksum, count, or time bounds changed.")


def validate_bundle(path, require_ready=True):
    directory = bundle_directory(path)
    manifest = parse_json(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )
    if (
        not isinstance(manifest, dict)
        or manifest.get("bundle_version") != 1
        or manifest.get("pipeline_version") != VERSION
        or manifest.get("file_family") != "FlightState"
        or manifest.get("target_table") != "public.flight_state_telemetry"
    ):
        raise PipelineError("Unsupported staging bundle; regenerate it.")

    cfg = validate_config(manifest["run_config"])
    if (
        manifest.get("components") != components()[2]
        or fingerprint(cfg) != manifest.get("config_sha256")
        or semantics(cfg, manifest["source"]["encoding"])
        != manifest.get("semantics_sha256")
    ):
        raise PipelineError("Staging code or configuration checksum changed.")

    if manifest.get("status") not in ("READY", "QUARANTINED"):
        raise PipelineError("Unknown staging status.")
    for name in ("records", "context"):
        if sha256_file(directory / f"{name}.jsonl") != manifest[
            f"{name}_sha256"
        ]:
            raise PipelineError(f"{name}.jsonl checksum changed.")

    if require_ready and manifest["status"] != "READY":
        raise PipelineError(
            f"Bundle is quarantined: {manifest.get('first_error')}"
        )

    if manifest["status"] == "READY":
        report = manifest["parser_report"]
        source = manifest["source"]
        if (
            not report.get("success")
            or not report.get("complete")
            or not report.get("line_accounting_matches")
            or report["sessions"] != 1
            or manifest["rejected_records"] != 0
            or type(manifest["records"]) is not int
            or manifest["records"] <= 0
            or report["counts"].get("record") != manifest["records"]
            or report["source_sha256"] != source["sha256"]
            or report["source_size_bytes"] != source["size_bytes"]
            or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        ):
            raise PipelineError("Invalid READY accounting or provenance.")
        if not manifest["schemas"]:
            raise PipelineError("No observed source schema.")
        for schema in manifest["schemas"]:
            names = schema["column_names"]
            if (
                not isinstance(names, list)
                or not all(isinstance(name, str) for name in names)
                or len(names) != len(set(names))
                or not REQUIRED_HEADERS.issubset(names)
                or not re.fullmatch(
                    r"[0-9a-f]{64}", schema["schema_signature"]
                )
            ):
                raise PipelineError("Invalid observed FlightState schema.")
        for _ in verified_rows(directory, manifest):
            pass
    return manifest


def stage_file(source, output, cfg, encoding="utf-8"):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_file():
        raise PipelineError(f"Source file does not exist: {source}")
    cfg = validate_config(cfg)
    source_hash = sha256_file(source)
    semantic_hash = semantics(cfg, encoding)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"{source_hash[:24]}-{semantic_hash[:16]}"

    if destination.exists():
        existing = validate_bundle(destination, require_ready=False)
        if (
            existing["source"]["sha256"] != source_hash
            or existing["semantics_sha256"] != semantic_hash
        ):
            raise PipelineError("Staging directory identity conflict.")
        return destination / "manifest.json", existing, True

    temporary = Path(tempfile.mkdtemp(prefix=".stage-", dir=output))
    parser_class, transformer_class, descriptor = components()
    parser = parser_class(quarantine=True)
    transformer = transformer_class(
        longitude_convention=cfg["longitude_convention"],
        missing_values=cfg["missing_values"],
    )
    clock = Clock(cfg)
    count = rejected = 0
    first_error = None
    first_time = last_time = None
    schemas = {}
    fatal = False

    try:
        with (
            (temporary / "records.jsonl").open(
                "w", encoding="utf-8", newline="\n"
            ) as records,
            (temporary / "context.jsonl").open(
                "w", encoding="utf-8", newline="\n"
            ) as context,
        ):
            try:
                for line in parser.iter_file(source, encoding=encoding):
                    if line.kind != "record":
                        context.write(canonical(line.to_dict()) + "\n")
                        if line.kind in ("rejected", "auxiliary"):
                            rejected += 1
                            first_error = first_error or (
                                line.message or "Unsupported auxiliary data."
                            )
                        continue
                    try:
                        if (
                            line.session_index != 1
                            or line.discriminator is not None
                            or line.schema is None
                            or not REQUIRED_HEADERS.issubset(line.schema.fields)
                        ):
                            raise PipelineError(
                                "Only single-session FlightState data is supported."
                            )
                        row = transformer.transform_row(
                            line.data,
                            line.source_line_number,
                            source_record_index=line.source_record_index,
                        )
                        check_precision(row)
                        timestamp = clock.resolve(row)
                        row["time"] = timestamp.isoformat()
                        records.write(canonical(row) + "\n")
                        count += 1
                        first_time = first_time or timestamp
                        last_time = timestamp
                        schemas[line.schema.schema_sha256] = {
                            "schema_signature": line.schema.schema_sha256,
                            "column_names": list(line.schema.fields),
                        }
                    except (ValueError, TypeError, OverflowError) as exc:
                        rejected += 1
                        first_error = first_error or str(exc)
                        context.write(canonical({
                            "kind": "transformation_rejected",
                            "source_line_number": line.source_line_number,
                            "source_record_index": line.source_record_index,
                            "raw_line": line.raw_line,
                            "message": str(exc),
                        }) + "\n")
            except Exception as exc:
                fatal = True
                first_error = first_error or str(exc)
                context.write(canonical({
                    "kind": "fatal_error",
                    "message": str(exc),
                }) + "\n")
            for stream in (records, context):
                stream.flush()
                os.fsync(stream.fileno())

        report = parser.report.to_dict()
        if (
            report["source_sha256"] != source_hash
            or report["sessions"] != 1
        ):
            fatal = True
            first_error = first_error or (
                "Source changed or contains multiple sessions."
            )
        if not count:
            first_error = first_error or "No accepted FlightState records."
        ready = (
            report["success"] and not fatal and not rejected and count > 0
        )
        manifest = {
            "bundle_version": 1,
            "pipeline_version": VERSION,
            "components": descriptor,
            "status": "READY" if ready else "QUARANTINED",
            "file_family": "FlightState",
            "target_table": "public.flight_state_telemetry",
            "finished_at": now().isoformat(),
            "source": {
                "path": str(source),
                "file_name": source.name,
                "sha256": source_hash,
                "size_bytes": report["source_size_bytes"],
                "encoding": encoding,
            },
            "run_config": cfg,
            "config_sha256": fingerprint(cfg),
            "semantics_sha256": semantic_hash,
            "records": count,
            "rejected_records": rejected,
            "first_error": first_error,
            "time_min": first_time.isoformat() if first_time else None,
            "time_max": last_time.isoformat() if last_time else None,
            "schemas": [schemas[key] for key in sorted(schemas)],
            "parser_report": report,
            "records_sha256": sha256_file(temporary / "records.jsonl"),
            "context_sha256": sha256_file(temporary / "context.jsonl"),
        }
        write_json(temporary / "manifest.json", manifest)
        try:
            os.rename(temporary, destination)
        except OSError:
            if not destination.exists():
                raise
            other = validate_bundle(destination, require_ready=False)
            if (
                other["source"]["sha256"] != source_hash
                or other["semantics_sha256"] != semantic_hash
            ):
                raise PipelineError("Concurrent staging identity conflict.")
            return destination / "manifest.json", other, True
        return destination / "manifest.json", manifest, False
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def safe_error(exc):
    if isinstance(exc, SQLAlchemyError):
        original = getattr(exc, "orig", None)
        code = (
            getattr(original, "sqlstate", None)
            or getattr(original, "pgcode", None)
            or "unavailable"
        )
        return (
            f"Database operation failed: {type(exc).__name__}; "
            f"SQLSTATE={code}. Check connection, permissions, and schema."
        )
    return f"{type(exc).__name__}: {exc}"


class Database:
    def __init__(self, database_url):
        url = make_url(database_url)
        if url.drivername in ("postgres", "postgresql"):
            driver = (
                "psycopg"
                if importlib.util.find_spec("psycopg") is not None
                else "psycopg2"
            )
            url = url.set(drivername=f"postgresql+{driver}")
        if (
            url.drivername not in (
                "postgresql+psycopg", "postgresql+psycopg2"
            )
            or url.database != "rrdata"
        ):
            raise PipelineError("DATABASE_URL must target PostgreSQL rrdata.")
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            hide_parameters=True,
            isolation_level="READ COMMITTED",
            connect_args={
                "connect_timeout": 15,
                "application_name": "macs_flightstate_pipeline",
            },
        )
        self.metadata = MetaData(schema="public")

    def close(self):
        self.engine.dispose()

    def table(self, name, connection):
        key = f"public.{name}"
        if key not in self.metadata.tables:
            Table(
                name, self.metadata, schema="public",
                autoload_with=connection, resolve_fks=False
            )
        return self.metadata.tables[key]

    def check(self, connection, require_write=False):
        if connection.execute(
            text("SELECT current_database()")
        ).scalar_one() != "rrdata":
            raise PipelineError("Connected database is not rrdata.")
        inspector = inspect(connection)
        if not inspector.has_table("macs_schema_versions", schema="public"):
            raise PipelineError("The v3 schema version table is missing.")
        markers = {
            row.component: (row.version, row.contract_sha256)
            for row in connection.execute(text(
                "SELECT component, version, contract_sha256 "
                "FROM public.macs_schema_versions"
            ))
        }
        for component, expected_hash in SCHEMA_MARKERS.items():
            if markers.get(component) != (3, expected_hash):
                raise PipelineError(f"{component} v3 schema marker mismatch.")

        for name, groups in LAYOUT.items():
            qualified = f"public.{name}"
            expected = {
                column: (kind.removesuffix("!"), kind.endswith("!"))
                for kind, columns in groups.items()
                for column in columns.split()
            }
            actual = {
                row.name: (row.data_type, row.required)
                for row in connection.execute(text(
                    "SELECT attname AS name, "
                    "format_type(atttypid, atttypmod) AS data_type, "
                    "attnotnull AS required "
                    "FROM pg_catalog.pg_attribute "
                    "WHERE attrelid=to_regclass(:table) "
                    "AND attnum>0 AND NOT attisdropped"
                ), {"table": qualified})
            }
            if actual != expected:
                raise PipelineError(
                    f"Column/type/nullability mismatch in {qualified}."
                )
            if inspector.get_pk_constraint(
                name, schema="public"
            )["constrained_columns"] != PRIMARY_KEYS[name]:
                raise PipelineError(f"Primary-key mismatch in {qualified}.")
            unique = {
                tuple(item["column_names"])
                for item in inspector.get_unique_constraints(
                    name, schema="public"
                )
            }
            if not set(UNIQUE_KEYS.get(name, [])).issubset(unique):
                raise PipelineError(f"Unique-key mismatch in {qualified}.")
            checks = {
                item["name"] for item in inspector.get_check_constraints(
                    name, schema="public"
                )
            }
            if not set(CHECK_NAMES[name].split()).issubset(checks):
                raise PipelineError(f"Missing CHECK constraint in {qualified}.")
            foreign = inspector.get_foreign_keys(name, schema="public")
            for table, columns, target, target_columns, on_delete in FOREIGN_KEYS:
                if table != name:
                    continue
                if not any(
                    tuple(item["constrained_columns"]) == columns
                    and item["referred_table"] == target
                    and tuple(item["referred_columns"]) == target_columns
                    and item.get("referred_schema") in (None, "public")
                    and (
                        item.get("options", {}).get("ondelete") or "NO ACTION"
                    ).upper() == on_delete
                    for item in foreign
                ):
                    raise PipelineError(
                        f"Foreign-key mismatch in {qualified}: {columns}."
                    )
            if connection.execute(text(
                "SELECT EXISTS (SELECT 1 FROM pg_constraint "
                "WHERE conrelid=to_regclass(:table) "
                "AND contype IN ('f','c') AND NOT convalidated)"
            ), {"table": qualified}).scalar_one():
                raise PipelineError(
                    f"Unvalidated constraint exists in {qualified}."
                )
            if connection.execute(text(
                "SELECT EXISTS (SELECT 1 FROM pg_index "
                "WHERE indrelid=to_regclass(:table) "
                "AND (NOT indisvalid OR NOT indisready))"
            ), {"table": qualified}).scalar_one():
                raise PipelineError(f"Invalid index exists in {qualified}.")

            privileges = ["SELECT"]
            if require_write:
                privileges.append("INSERT")
                if name in UPDATE_TABLES:
                    privileges.append("UPDATE")
            for privilege in privileges:
                allowed = connection.execute(text(
                    "SELECT has_table_privilege("
                    "current_user,:table,:privilege)"
                ), {
                    "table": qualified, "privilege": privilege
                }).scalar_one()
                if not allowed:
                    raise PipelineError(
                        f"Login needs {privilege} on {qualified}."
                    )
            if require_write and len(PRIMARY_KEYS[name]) == 1:
                sequence = connection.execute(text(
                    "SELECT pg_get_serial_sequence(:table,:column)"
                ), {
                    "table": qualified,
                    "column": PRIMARY_KEYS[name][0],
                }).scalar_one()
                if sequence and not connection.execute(text(
                    "SELECT has_sequence_privilege("
                    "current_user,:sequence,'USAGE') OR "
                    "has_sequence_privilege(current_user,:sequence,'UPDATE')"
                ), {"sequence": sequence}).scalar_one():
                    raise PipelineError(
                        f"Login needs sequence access for {qualified}."
                    )

        return {
            "database": "rrdata",
            "schema": "public",
            "tables_verified": sorted(LAYOUT),
            "extensions": dict(connection.execute(text(
                "SELECT extname,extversion FROM pg_extension "
                "WHERE extname IN ('timescaledb','postgis')"
            )).all()),
        }

    def fact_count(self, connection, source_id):
        facts = self.table("flight_state_telemetry", connection)
        return connection.execute(
            select(func.count()).select_from(facts).where(
                facts.c.source_file_id == source_id
            )
        ).scalar_one()

    def check_run(self, existing, cfg):
        for name in (
            "experiment_date", "source_timezone",
            "experiment_condition", "scenario_name"
        ):
            if name in cfg:
                expected = (
                    date.fromisoformat(cfg[name])
                    if name == "experiment_date" else cfg[name]
                )
                if existing[name] != expected:
                    raise PipelineError(
                        f"Existing run_key has conflicting {name}."
                    )

    def preview(self, connection, manifest):
        cfg = manifest["run_config"]
        runs = self.table("simulation_runs", connection)
        files = self.table("source_files", connection)
        run = connection.execute(
            select(runs).where(runs.c.run_key == cfg["run_key"])
        ).mappings().first()
        if run:
            self.check_run(run, cfg)
        existing = connection.execute(
            select(files).where(
                files.c.sha256 == manifest["source"]["sha256"]
            )
        ).mappings().first()
        if not existing:
            return "LOAD"
        if existing["file_family"] not in (None, "FlightState"):
            raise PipelineError("Source is registered to another file family.")
        if existing["simulation_run_id"] is not None and (
            run is None
            or existing["simulation_run_id"] != run["simulation_run_id"]
        ):
            raise PipelineError("Source is registered to a different run.")
        count = self.fact_count(connection, existing["source_file_id"])
        if existing["processing_status"] == "LOADED":
            saved = existing["metadata"].get(METADATA_KEY, {})
            if (
                not isinstance(saved, dict)
                or saved.get("semantics_sha256")
                != manifest["semantics_sha256"]
                or saved.get("records_sha256")
                != manifest["records_sha256"]
            ):
                raise PipelineError(
                    "Source is already loaded with different or "
                    "unrecorded transformation context."
                )
            if count != manifest["records"] or count != existing["loaded_records"]:
                raise PipelineError("Existing loaded-source counts disagree.")
            return "SKIP"
        if count or existing["loaded_records"]:
            raise PipelineError(
                "A non-LOADED source already has rows; reconcile it first."
            )
        return "LOAD"

    def run_id(self, connection, manifest):
        cfg = manifest["run_config"]
        runs = self.table("simulation_runs", connection)
        minimum = utc_datetime(manifest["time_min"])
        maximum = utc_datetime(manifest["time_max"])
        values = {
            "run_key": cfg["run_key"],
            "experiment_date": date.fromisoformat(cfg["experiment_date"]),
            "source_timezone": cfg["source_timezone"],
            "started_at": minimum,
            "ended_at": maximum,
        }
        for name in ("experiment_condition", "scenario_name", "notes"):
            if name in cfg:
                values[name] = cfg[name]
        connection.execute(
            pg_insert(runs).values(**values).on_conflict_do_nothing(
                index_elements=[runs.c.run_key]
            )
        )
        existing = connection.execute(
            select(runs).where(
                runs.c.run_key == cfg["run_key"]
            ).with_for_update()
        ).mappings().one()
        self.check_run(existing, cfg)
        identifier = existing["simulation_run_id"]
        connection.execute(
            update(runs).where(
                runs.c.simulation_run_id == identifier
            ).values(
                started_at=func.least(runs.c.started_at, minimum),
                ended_at=func.greatest(runs.c.ended_at, maximum),
                updated_at=func.clock_timestamp(),
            )
        )
        return identifier

    def success(self, connection, pipeline_id, attempt, manifest, result, started):
        events = self.table("processing_events", connection)
        runs = self.table("pipeline_runs", connection)
        connection.execute(events.insert().values(
            pipeline_run_id=pipeline_id,
            source_file_id=result["source_file_id"],
            stage="LOAD",
            status="SKIPPED" if result["status"] == "SKIPPED" else "SUCCEEDED",
            started_at=started,
            finished_at=func.clock_timestamp(),
            records_read=manifest["records"],
            records_written=result["records_written"],
            records_rejected=0,
            message="Verified FlightState load completed.",
            details={
                "attempt_id": attempt,
                "source_sha256": manifest["source"]["sha256"],
                "semantics_sha256": manifest["semantics_sha256"],
                "result": result,
            },
        ))
        connection.execute(
            update(runs).where(
                runs.c.pipeline_run_id == pipeline_id
            ).values(
                status="SUCCEEDED",
                files_succeeded=1,
                files_failed=0,
                records_written=result["records_written"],
                finished_at=func.clock_timestamp(),
            )
        )

    def lock_source(self, connection, source_hash):
        connection.execute(text("SET LOCAL lock_timeout='30s'"))
        key = int.from_bytes(
            bytes.fromhex(source_hash)[:8], "big", signed=True
        )
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": key}
        )

    def load_file(self, connection, path, manifest, pipeline_id, attempt, batch):
        connection.execute(text("SET LOCAL timezone='UTC'"))
        self.lock_source(connection, manifest["source"]["sha256"])
        started = connection.execute(
            select(func.clock_timestamp())
        ).scalar_one()
        action = self.preview(connection, manifest)
        files = self.table("source_files", connection)
        existing = connection.execute(
            select(files).where(
                files.c.sha256 == manifest["source"]["sha256"]
            ).with_for_update()
        ).mappings().first()

        if action == "SKIP":
            result = {
                "status": "SKIPPED",
                "source_file_id": existing["source_file_id"],
                "simulation_run_id": existing["simulation_run_id"],
                "records_written": 0,
                "records_existing": manifest["records"],
            }
            self.success(
                connection, pipeline_id, attempt, manifest, result, started
            )
            return result

        run_id = self.run_id(connection, manifest)
        metadata = dict(existing["metadata"]) if existing else {}
        metadata[METADATA_KEY] = {
            "version": VERSION,
            "semantics_sha256": manifest["semantics_sha256"],
            "records_sha256": manifest["records_sha256"],
            "config_sha256": manifest["config_sha256"],
            "run_config": manifest["run_config"],
            "stage_manifest": str(Path(path).resolve()),
        }
        metadata["parser_report"] = manifest["parser_report"]
        values = {
            "simulation_run_id": run_id,
            "file_name": manifest["source"]["file_name"],
            "original_path": manifest["source"]["path"],
            "extracted_path": manifest["source"]["path"],
            "file_family": "FlightState",
            "file_extension": Path(manifest["source"]["file_name"]).suffix,
            "file_size_bytes": manifest["source"]["size_bytes"],
            "schema_signature": fingerprint(manifest["schemas"]),
            "encoding": manifest["source"]["encoding"],
            "delimiter": "\t",
            "processing_status": "TRANSFORMED",
            "total_lines": manifest["parser_report"]["physical_lines"],
            "parsed_records": manifest["records"],
            "rejected_records": 0,
            "loaded_records": 0,
            "first_error": None,
            "parsed_at": utc_datetime(manifest["finished_at"]),
            "validated_at": utc_datetime(manifest["finished_at"]),
            "transformed_at": utc_datetime(manifest["finished_at"]),
            "metadata": metadata,
        }
        if existing:
            source_id = existing["source_file_id"]
            connection.execute(
                update(files).where(
                    files.c.source_file_id == source_id
                ).values(**values)
            )
        else:
            source_id = connection.execute(
                files.insert().values(
                    sha256=manifest["source"]["sha256"], **values
                ).returning(files.c.source_file_id)
            ).scalar_one()

        registry = self.table("source_schema_registry", connection)
        for schema in manifest["schemas"]:
            statement = pg_insert(registry).values(
                file_family="FlightState",
                section_name="FlightState",
                schema_signature=schema["schema_signature"],
                column_names=schema["column_names"],
                column_count=len(schema["column_names"]),
                first_source_file_id=source_id,
                is_approved=False,
            )
            connection.execute(statement.on_conflict_do_update(
                index_elements=[
                    registry.c.file_family,
                    registry.c.section_name,
                    registry.c.schema_signature,
                ],
                set_={"last_seen_at": func.clock_timestamp()},
            ))

        aircraft = self.table("aircraft", connection)
        facts = self.table("flight_state_telemetry", connection)
        identities = {}
        pending = []
        written = 0

        for row in verified_rows(path, manifest):
            callsign = row["callsign"]
            timestamp = row["time"]
            if callsign not in identities:
                connection.execute(
                    pg_insert(aircraft).values(
                        simulation_run_id=run_id,
                        callsign=callsign,
                        flight_rules=row["flight_rules"],
                        first_seen_at=timestamp,
                        last_seen_at=timestamp,
                    ).on_conflict_do_nothing(index_elements=[
                        aircraft.c.simulation_run_id, aircraft.c.callsign
                    ])
                )
                aircraft_id = connection.execute(
                    select(aircraft.c.aircraft_id).where(
                        aircraft.c.simulation_run_id == run_id,
                        aircraft.c.callsign == callsign,
                    )
                ).scalar_one()
                identities[callsign] = {
                    "p_id": aircraft_id,
                    "p_first": timestamp,
                    "p_last": timestamp,
                }
            identity = identities[callsign]
            identity["p_first"] = min(identity["p_first"], timestamp)
            identity["p_last"] = max(identity["p_last"], timestamp)
            row.update(
                simulation_run_id=run_id,
                source_file_id=source_id,
                aircraft_id=identity["p_id"],
            )
            for name in ("utc_time", "log_time", "stamp_time"):
                if row[name] is not None:
                    row[name] = time.fromisoformat(row[name])
            pending.append(row)
            if len(pending) >= batch:
                connection.execute(facts.insert(), pending)
                written += len(pending)
                pending = []
        if pending:
            connection.execute(facts.insert(), pending)
            written += len(pending)

        if (
            written != manifest["records"]
            or self.fact_count(connection, source_id) != written
        ):
            raise PipelineError("Inserted row count differs from staged count.")

        connection.execute(
            update(aircraft).where(
                aircraft.c.aircraft_id == bindparam("p_id")
            ).values(
                first_seen_at=func.least(
                    aircraft.c.first_seen_at, bindparam("p_first")
                ),
                last_seen_at=func.greatest(
                    aircraft.c.last_seen_at, bindparam("p_last")
                ),
                updated_at=func.clock_timestamp(),
            ),
            list(identities.values()),
        )
        connection.execute(
            update(files).where(
                files.c.source_file_id == source_id
            ).values(
                processing_status="LOADED",
                loaded_records=written,
                loaded_at=func.clock_timestamp(),
                updated_at=func.clock_timestamp(),
            )
        )
        validation = self.table("validation_results", connection)
        connection.execute(validation.insert().values(
            pipeline_run_id=pipeline_id,
            source_file_id=source_id,
            rule_name="flightstate_bundle_integrity",
            passed=True,
            severity="INFO",
            section_name="FlightState",
            message=(
                "Complete parse, source positions, configuration, typed values, "
                "checksums, and inserted count verified."
            ),
            expected_value=str(manifest["records"]),
            actual_value=str(written),
        ))
        result = {
            "status": "LOADED",
            "source_file_id": source_id,
            "simulation_run_id": run_id,
            "records_written": written,
        }
        self.success(
            connection, pipeline_id, attempt, manifest, result, started
        )
        return result


def load_bundle(db, path, commit=False, batch=500, receipt_directory=None):
    if type(batch) is not int or not 1 <= batch <= 5000:
        raise PipelineError("batch_size must be between 1 and 5000.")
    path = bundle_directory(path) / "manifest.json"
    manifest = validate_bundle(path)

    with db.engine.begin() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        checked = db.check(connection, require_write=commit)
        action = db.preview(connection, manifest)

    base = {
        "mode": "COMMIT" if commit else "DRY_RUN",
        "manifest": str(path),
        "source_sha256": manifest["source"]["sha256"],
        "run_key": manifest["run_config"]["run_key"],
        "records": manifest["records"],
        "time_min": manifest["time_min"],
        "time_max": manifest["time_max"],
        "database_check": checked,
    }
    if not commit:
        return {
            **base, "status": "VALIDATED", "action": action,
            "records_written": 0,
        }

    attempt = str(uuid4())
    with db.engine.begin() as connection:
        runs = db.table("pipeline_runs", connection)
        pipeline_id = connection.execute(
            runs.insert().values(
                run_uuid=uuid4(),
                trigger_type="MANUAL",
                status="RUNNING",
                host_name=socket.gethostname(),
                process_id=os.getpid(),
                code_version=VERSION,
                files_seen=1,
                details={
                    "attempt_id": attempt,
                    "stage": "LOAD",
                    "file_family": "FlightState",
                    "manifest": str(path),
                },
            ).returning(runs.c.pipeline_run_id)
        ).scalar_one()

    try:
        with db.engine.begin() as connection:
            result = db.load_file(
                connection, path, manifest, pipeline_id, attempt, batch
            )
    except Exception as exc:
        error = safe_error(exc)
        try:
            with db.engine.begin() as connection:
                # Wait for any original transaction to finish before deciding
                # whether its commit succeeded.
                db.lock_source(connection, manifest["source"]["sha256"])
                events = db.table("processing_events", connection)
                recovered = None
                for event in connection.execute(
                    select(events).where(
                        events.c.pipeline_run_id == pipeline_id,
                        events.c.stage == "LOAD",
                        events.c.status.in_(["SUCCEEDED", "SKIPPED"]),
                    )
                ).mappings():
                    if event["details"].get("attempt_id") == attempt:
                        recovered = event["details"]["result"]
                        break
                if recovered is not None:
                    result = {**recovered, "commit_reconciled": True}
                else:
                    connection.execute(events.insert().values(
                        pipeline_run_id=pipeline_id,
                        stage="LOAD",
                        status="FAILED",
                        finished_at=func.clock_timestamp(),
                        message=error,
                        details={
                            "attempt_id": attempt,
                            "source_sha256": manifest["source"]["sha256"],
                            "manifest": str(path),
                        },
                    ))
                    runs = db.table("pipeline_runs", connection)
                    connection.execute(
                        update(runs).where(
                            runs.c.pipeline_run_id == pipeline_id
                        ).values(
                            status="FAILED",
                            files_failed=1,
                            finished_at=func.clock_timestamp(),
                            message=error,
                        )
                    )
                    result = {
                        "status": "FAILED",
                        "records_written": 0,
                        "error": error,
                    }
        except Exception as recovery_error:
            return {
                **base,
                "status": "UNKNOWN",
                "pipeline_run_id": pipeline_id,
                "records_written": None,
                "error": error,
                "recovery_error": safe_error(recovery_error),
                "next_action": (
                    "Restore database connectivity and rerun this exact bundle. "
                    "The commit outcome could not be established."
                ),
            }

    result = {**base, **result, "pipeline_run_id": pipeline_id}
    if receipt_directory and result["status"] in ("LOADED", "SKIPPED"):
        try:
            write_json(
                Path(receipt_directory) / f"load-{attempt}.json",
                {"finished_at": now().isoformat(), **result},
            )
        except OSError as exc:
            result["receipt_warning"] = (
                f"Database commit succeeded, but receipt writing failed: {exc}"
            )
    return result


def emit(report, report_path=None):
    if report_path is not None:
        try:
            report["report_path"] = str(Path(report_path).resolve())
            write_json(report_path, report)
        except OSError as exc:
            report["report_warning"] = str(exc)
    print(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))


def configure(path):
    path = Path(path)
    if path.exists():
        raise PipelineError(
            f"{path} already exists; edit it or choose another --run-config."
        )
    print("Enter confirmed metadata for one logical simulation run.")
    cfg = {
        "config_version": 1,
        "run_key": input("Stable run key: ").strip(),
        "experiment_date": input("Experiment date (YYYY-MM-DD): ").strip(),
        "source_timezone": "UTC",
        "longitude_convention": input(
            "Longitude convention [east_positive / west_positive]: "
        ).strip(),
        "missing_values": {},
    }
    mode = input(
        "Clock mode [utc_clock / simulation_elapsed_ms]: "
    ).strip()
    if mode == "utc_clock":
        cfg["time_policy"] = {
            "mode": mode,
            "utc_date": input(
                "UTC date of FIRST data record (YYYY-MM-DD): "
            ).strip(),
            "midnight_rollover": input(
                "Midnight policy [reject / advance_at_midnight]: "
            ).strip(),
        }
    elif mode == "simulation_elapsed_ms":
        cfg["time_policy"] = {
            "mode": mode,
            "simulation_start_utc": input(
                "UTC timestamp at SIM_TIME=0 (YYYY-MM-DDTHH:MM:SSZ): "
            ).strip(),
        }
    else:
        raise PipelineError("Unsupported clock mode.")
    write_json(path, validate_config(cfg))
    print(f"Saved configuration: {path.resolve()}")


def transform_main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate and stage one single-run FlightState log."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--configure", action="store_true")
    mode.add_argument("--check-components", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument(
        "--run-config", type=Path,
        default=ROOT / "config/flightstate_run.json"
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--encoding", default="utf-8")
    args = parser.parse_args(argv)

    try:
        directories = paths()
        if args.check_components:
            emit({
                "status": "OK",
                "parser_path": str(PARSER_PATH),
                "transformer_path": str(TRANSFORMER_PATH),
                "components": components()[2],
            })
            return 0
        if args.configure:
            configure(args.run_config)
            return 0
        if args.input is None:
            parser.error("--input is required unless using a configuration check.")
        cfg = validate_config(parse_json(
            args.run_config.read_text(encoding="utf-8-sig")
        ))
        path, manifest, reused = stage_file(
            args.input, args.output_dir or directories["staged"],
            cfg, encoding=args.encoding
        )
        report = {
            "status": manifest["status"],
            "manifest": str(path),
            "records": manifest["records"],
            "rejected_records": manifest["rejected_records"],
            "first_error": manifest["first_error"],
            "reused": reused,
        }
        emit(
            report,
            directories["metadata"] / f"transform-{uuid4()}.json"
        )
        return 0 if manifest["status"] == "READY" else 2
    except Exception as exc:
        print(f"TRANSFORM FAILED: {safe_error(exc)}", file=sys.stderr)
        return 1


def load_main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Validate or load one FlightState bundle into rrdata. "
            "Default: database dry run."
        )
    )
    parser.add_argument("--input", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-db", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args(argv)
    db = None

    try:
        directories = paths()
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise PipelineError(
                f"Set DATABASE_URL in {ROOT / '.env'} or the environment."
            )
        db = Database(database_url)
        if args.check_db:
            with db.engine.begin() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                emit(db.check(connection))
            return 0
        if args.input is None:
            parser.error("--input is required unless using --check-db.")
        report = load_bundle(
            db, args.input, commit=args.commit, batch=args.batch_size,
            receipt_directory=directories["processed"],
        )
        emit(
            report,
            directories["metadata"] / f"load-{uuid4()}.json"
        )
        return 0 if report["status"] in (
            "VALIDATED", "LOADED", "SKIPPED"
        ) else 2
    except Exception as exc:
        print(f"LOAD FAILED: {safe_error(exc)}", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()