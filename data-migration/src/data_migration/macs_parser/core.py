"""Loss-aware MACS text parser, Python 3.10+, standard library only.

Parse source structure here; convert units/types in a family transformer and
write to PostgreSQL in a separate loader. See README.md for the public API,
format coverage, Custom header mismatch, and migration from the original core.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__version__ = "2.0.0"

DISCRIMINATOR_MAPPING = {
    "GLOBAL_DATA": "GLOBAL_MAP",
    "TRAJPOINT_DATA": "TRAJPOINT_MAP",
    "OPERATOR-ACTION": "WKLOAD-KEYPAD-HDR",
}
KNOWN_DISCRIMINATORS = frozenset({
    "SECTOR_DATA", "COMPLEXITY_DATA", "ATC_DATA", "AC_DATA",
    "WKLOAD_DATA", "BOUNDARY_CHANGE", "GLOBAL_MAP", "TRAJPOINT_MAP",
    "WKLOAD-KEYPAD-HDR",
})
SECTOR_FIELDS = (
    "NUM", "VOLUME_NM", "ASPECT_RATIO", "MIN ALT_FT", "MAX_ALT_FT",
    "NUM_VERTECES", "VERTEX_X,VERTEX_Y,VERTEX_LAT,VERTEX_LON",
)
_RUN = re.compile(r"run(?: +[^\t]*)?\Z")
_EVENT = re.compile(
    r"(?:Controller (?:Signed-On:|Signed-Off:|sign-in(?:\b|:)|sign-out(?:\b|:))"
    r"|Criteria\s*==)"
)
_METADATA = re.compile(
    r"(?:date |scenario |bundle scenario:|experiment condition|macs version"
    r"|file name:|FEP Url:|FEP Version:|Schema File\s*:|USS Url\s*:)"
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def header_fingerprint(declarations: Iterable[str]) -> str:
    """SHA-256 of the exact ordered header declaration strings, without EOLs."""
    return hashlib.sha256(_json(list(declarations)).encode("utf-8")).hexdigest()


def _fields(tokens: Iterable[str]) -> tuple[str, ...]:
    names = list(tokens)
    if not all(isinstance(v, str) for v in names):
        raise ValueError("Column names must be strings")
    names = [v.strip() for v in names]
    while names and names[-1] == "":
        names.pop()  # Unnamed trailing padding; the source header is retained.
    if not names or any(not v for v in names):
        raise ValueError("Empty or unnamed interior column; cannot assign values safely")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate column names would overwrite source values")
    if any("\x00" in v or "\r" in v or "\n" in v for v in names):
        raise ValueError("Column names contain a forbidden control character")
    return tuple(names)


@dataclass(frozen=True)
class Schema:
    fields: tuple[str, ...]
    discriminator: str | None
    source_line_number: int
    header_block_sha256: str
    schema_sha256: str
    origin: str = "declared"


@dataclass(frozen=True)
class ParsedLine:
    """One physical source line; metadata never shares a namespace with data."""

    kind: str
    source_line_number: int
    session_index: int
    raw_line: str
    line_ending: str = ""
    raw_values: tuple[str, ...] = ()
    source_record_index: int = 1
    data: dict[str, Any] | None = None
    schema: Schema | None = None
    discriminator: str | None = None
    layout: str | None = None
    code: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MacsParseError(ValueError):
    def __init__(self, source: str, issue: ParsedLine):
        self.source = source
        self.issue = issue
        super().__init__(
            f"{source}:{issue.source_line_number} (session {issue.session_index}) "
            f"[{issue.code}] {issue.message}"
        )


@dataclass
class ParseReport:
    source: str
    parser_version: str = __version__
    complete: bool = False
    source_sha256: str | None = None
    source_size_bytes: int | None = None
    encoding: str | None = None
    physical_lines: int = 0
    sessions: int = 0
    counts: Counter = field(default_factory=Counter)
    records_by_type: Counter = field(default_factory=Counter)
    issue_codes: Counter = field(default_factory=Counter)
    header_blocks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # asdict reconstructs Counter from pairs, not from a mapping.
        for name in ("counts", "records_by_type", "issue_codes"):
            d[name] = dict(getattr(self, name))
        d["structurally_valid"] = self.complete and self.counts["rejected"] == 0
        d["all_data_lines_have_named_fields"] = d["structurally_valid"] and self.counts["auxiliary"] == 0
        d["success"] = d["all_data_lines_have_named_fields"]
        d["line_accounting_matches"] = sum(self.counts.values()) == self.physical_lines
        return d


class MacsParser:
    """Single-use streaming parser; default stops on the first bad record.

    quarantine=True emits rejected lines instead. Structural header errors,
    decoding failures, and source mutation always abort the file. Consume the
    iterator to completion before committing a load. A partial iteration is
    not a successful file. No dates, units, missing values, or types are guessed.
    """

    def __init__(
        self, *, delimiter: str = "\t", mode: str = "auto",
        quarantine: bool = False, max_line_chars: int = 2_000_000,
        max_header_lines: int = 1000, profile: Mapping[str, Any] | None = None,
    ):
        if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in "\r\n\x00":
            raise ValueError("delimiter must be one non-newline, non-NUL character")
        if mode not in {"auto", "single", "multiplex"}:
            raise ValueError("mode must be auto, single, or multiplex")
        if type(max_line_chars) is not int or max_line_chars < 1:
            raise ValueError("max_line_chars must be a positive integer")
        if type(max_header_lines) is not int or max_header_lines < 1:
            raise ValueError("max_header_lines must be a positive integer")
        self.delimiter, self.mode, self.quarantine = delimiter, mode, quarantine
        self.max_line_chars, self.max_header_lines = max_line_chars, max_header_lines
        self.profile = self._validate_profile(profile)
        self.report = ParseReport("<unopened>")
        self._used = False

    @staticmethod
    def _validate_profile(profile: Mapping[str, Any] | None) -> dict[str, Any]:
        if profile is None:
            return {}
        if not isinstance(profile, Mapping) or set(profile) != {"profile_version", "schema_overrides"}:
            raise ValueError("Profile needs only profile_version and schema_overrides")
        if type(profile["profile_version"]) is not int or profile["profile_version"] != 1:
            raise ValueError("Unsupported profile_version")
        overrides = profile["schema_overrides"]
        if not isinstance(overrides, dict):
            raise ValueError("schema_overrides must be an object")
        for fingerprint, spec in overrides.items():
            if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                raise ValueError("An override key must be a lowercase header SHA-256")
            if not isinstance(spec, dict) or set(spec) != {"mode", "schemas", "reason", "approved_by"}:
                raise ValueError("Override needs mode, schemas, reason, and approved_by")
            if not isinstance(spec["mode"], str) or spec["mode"] not in {"single", "multiplex"}:
                raise ValueError("Override mode must be single or multiplex")
            if not all(isinstance(spec[k], str) and spec[k].strip() for k in ("reason", "approved_by")):
                raise ValueError("An override needs a documented reason and source-owner approval")
            if not isinstance(spec["schemas"], list) or not spec["schemas"]:
                raise ValueError("Override schemas must be a nonempty list of column-name lists")
            for names in spec["schemas"]:
                if not isinstance(names, list):
                    raise ValueError("Each override schema must be a list")
                _fields(names)
        return json.loads(_json(overrides))

    def _error(self, line: ParsedLine, code: str, message: str, *, fatal: bool = False) -> ParsedLine:
        issue = ParsedLine(
            "rejected", line.source_line_number, line.session_index, line.raw_line,
            line.line_ending, line.raw_values, code=code, message=message,
        )
        if fatal or not self.quarantine:
            self.report.complete = False
            raise MacsParseError(self.report.source, issue)
        return issue

    def _count(self, line: ParsedLine) -> ParsedLine:
        self.report.counts[line.kind] += 1
        if line.kind == "record":
            self.report.records_by_type[line.discriminator or "single"] += 1
        if line.kind == "rejected":
            self.report.issue_codes[line.code] += 1
        return line

    def _build_schemas(self, declarations: list[ParsedLine], end: ParsedLine) -> tuple[list[Schema], str]:
        if not declarations:
            self._error(end, "MISSING_SCHEMA", "END HEADER has no column declarations", fatal=True)
        fingerprint = header_fingerprint(l.raw_line for l in declarations)
        spec = self.profile.get(fingerprint)
        candidates = [list(l.raw_values) for l in declarations]
        mode = self.mode
        origin = "declared"
        if spec:
            candidates, mode, origin = spec["schemas"], spec["mode"], "approved_override"
        if mode == "auto":
            heads = [c[0].strip() for c in candidates]
            mode = "multiplex" if (
                all(h in KNOWN_DISCRIMINATORS for h in heads)
                or (len(set(heads)) > 1 and len(set(heads)) == len(heads))
            ) else "single"
        schemas: list[Schema] = []
        seen = set()
        try:
            for i, candidate in enumerate(candidates):
                names = _fields(candidate)
                tag = names[0] if mode == "multiplex" else None
                fields = _fields(names[1:] if tag is not None else names)
                signature = hashlib.sha256(_json([tag, fields]).encode("utf-8")).hexdigest()
                if signature in seen:
                    continue
                seen.add(signature)
                schemas.append(Schema(
                    fields, tag, declarations[i].source_line_number if not spec else end.source_line_number,
                    fingerprint, signature, origin,
                ))
        except (ValueError, TypeError) as exc:
            self._error(end, "INVALID_SCHEMA", str(exc), fatal=True)
        block = {
            "session_index": end.session_index, "end_header_line": end.source_line_number,
            "header_block_sha256": fingerprint, "mode": mode,
            "declarations": [{"source_line_number": l.source_line_number, "raw_line": l.raw_line}
                             for l in declarations],
            "schemas": [asdict(s) for s in schemas],
        }
        if spec:
            block["override"] = spec
        self.report.header_blocks.append(block)
        return schemas, mode

    @staticmethod
    def _match_values(schema: Schema, values: tuple[str, ...]) -> tuple[dict[str, Any], str] | None:
        fields = schema.fields
        if schema.discriminator == "SECTOR_DATA" and fields == SECTOR_FIELDS:
            if len(values) < 6:
                return None
            count = values[5]
            if count == "NO_VERTEX" or (values[0] == "COMBINED" and count == ""):
                n = 0
                layout = "sector_no_vertex" if count else "sector_combined"
            elif re.fullmatch(r"[0-9]{1,9}", count):
                n, layout = int(count), "sector_vertices"
            else:
                return None
            if len(values) < 6 + n or any(v.strip() for v in values[6 + n:]):
                return None
            vertices = values[6:6 + n]
            if any(len(v.split(",")) != 4 or any(not x.strip() for x in v.split(",")) for v in vertices):
                return None
            data = dict(zip(fields[:6], values[:6]))
            data[fields[6]] = list(vertices)  # Keep coordinate strings and signs unchanged.
            return data, layout
        n = len(fields)
        if len(values) < n or any(v.strip() for v in values[n:]):
            return None
        return dict(zip(fields, values[:n])), "fixed"

    def _parse_record(self, line: ParsedLine, schemas: list[Schema], mode: str) -> ParsedLine:
        if "\x00" in line.raw_line:
            return self._error(line, "NUL_IN_RECORD", "NUL is not valid PostgreSQL text/JSONB")
        values = line.raw_values
        tag = DISCRIMINATOR_MAPPING.get(values[0], values[0]) if mode == "multiplex" else None
        choices = [s for s in schemas if s.discriminator == tag]
        if not choices:
            # This exact auxiliary layout is present in both supplied CompMet files,
            # but is not declared by their headers. Preserve it without inventing names.
            if tag == "DATA_BLOCK_MODE" and any(s.discriminator == "SECTOR_DATA" for s in schemas):
                if len(values) != 5:
                    return self._error(line, "AUXILIARY_WIDTH", "DATA_BLOCK_MODE needs its observed five raw positions")
                return ParsedLine(
                    "auxiliary", line.source_line_number, line.session_index,
                    line.raw_line, line.line_ending, values, discriminator=tag,
                    code="UNDECLARED_AUXILIARY", message="Raw positions retained; no header names or database mapping assigned",
                )
            return self._error(line, "UNKNOWN_DISCRIMINATOR", f"No declared schema for {tag!r}")
        payload = values[1:] if mode == "multiplex" else values
        if mode == "multiplex" and payload and payload[0] in {s.fields[0] for s in choices}:
            return self._error(line, "UNANNOUNCED_SCHEMA", "Changed schema requires a new run header or an approved header profile")
        matches = [(s, m) for s in choices if (m := self._match_values(s, payload)) is not None]
        if len(matches) != 1:
            code = "AMBIGUOUS_SCHEMA" if matches else "ROW_SCHEMA_MISMATCH"
            expected = [len(s.fields) for s in choices]
            detail = " Multiple declarations fit; a source-approved profile is required." if matches else ""
            return self._error(line, code,
                f"Got {len(payload)} values; candidate named widths {expected}."
                " Only surplus blank padding or declared sector vertex groups are allowed." + detail)
        schema, (data, layout) = matches[0]
        return ParsedLine(
            "record", line.source_line_number, line.session_index, line.raw_line,
            line.line_ending, values, data=data, schema=schema, discriminator=tag, layout=layout,
        )

    def iter_lines(self, lines: Iterable[str], *, source: str = "<memory>") -> Iterator[ParsedLine]:
        """Input items must be individual physical lines, optionally with CR/LF EOL."""
        if self._used:
            raise RuntimeError("Create a new MacsParser for each file")
        self._used = True
        self.report.source = source
        in_header, saw_run = True, False
        header_line_count = 0
        declarations: list[ParsedLine] = []
        schemas: list[Schema] = []
        schema_texts: set[str] = set()
        session, active_mode = 1, self.mode
        repeated_header = False
        last = ParsedLine("header", 0, session, "")
        for number, physical in enumerate(lines, 1):
            self.report.physical_lines = number
            self.report.sessions = session
            if not isinstance(physical, str):
                raise TypeError("iter_lines requires text lines")
            ending = "\r\n" if physical.endswith("\r\n") else (physical[-1:] if physical.endswith(("\r", "\n")) else "")
            raw = physical[:-len(ending)] if ending else physical
            # A BOM is retained in raw_line but not mistaken for a header token.
            text = raw.removeprefix("\ufeff") if number == 1 else raw
            values = tuple(text.split(self.delimiter))
            last = ParsedLine("header", number, session, raw, ending, values)
            if len(raw) > self.max_line_chars:
                self._error(last, "LINE_TOO_LONG", f"Physical line exceeds {self.max_line_chars} characters", fatal=True)
            if "\n" in raw or "\r" in raw:
                self._error(last, "NOT_PHYSICAL_LINES", "Input item includes an embedded physical newline", fatal=True)
            try:
                raw.encode("utf-8", errors="strict")
            except UnicodeError:
                self._error(last, "INVALID_UNICODE", "Input contains an unpaired Unicode surrogate", fatal=True)
            run_marker = bool(_RUN.fullmatch(text.strip()))
            if run_marker and not in_header:
                session += 1
                self.report.sessions = session
                last = ParsedLine("header", number, session, raw, ending, values)
                in_header, saw_run, header_line_count = True, False, 0
                declarations, schemas, schema_texts = [], [], set()
                repeated_header = False
            if in_header:
                header_line_count += 1
                if header_line_count > self.max_header_lines:
                    self._error(last, "HEADER_TOO_LONG", "END HEADER not found within header limit", fatal=True)
                if "\x00" in raw:
                    self._error(last, "INVALID_HEADER", "NUL in header", fatal=True)
                if run_marker:
                    if saw_run or declarations:
                        self._error(last, "MISSING_END_HEADER", "New run before the previous END HEADER", fatal=True)
                    saw_run = True
                elif text.strip() == "END HEADER":
                    schemas, active_mode = self._build_schemas(declarations, last)
                    schema_texts = {l.raw_line for l in declarations}
                    in_header = False
                elif self.delimiter in text and not _METADATA.match(text):
                    declarations.append(last)
                yield self._count(last)
                continue
            if text in schema_texts:
                repeated_header = True
                yield self._count(last)
                continue
            if text.strip() == "END HEADER":
                if not repeated_header:
                    yield self._count(self._error(last, "UNEXPECTED_END_HEADER", "No repeated schema declaration precedes this marker"))
                else:
                    repeated_header = False
                    yield self._count(last)
                continue
            repeated_header = False
            if self.delimiter not in text and not text.strip():
                result = ParsedLine("blank", number, session, raw, ending, values)
            elif _EVENT.match(text):
                result = ParsedLine("event", number, session, raw, ending, values)
            elif active_mode == "single" and values[0] in {s.fields[0] for s in schemas}:
                result = self._error(last, "UNANNOUNCED_SCHEMA", "Changed schema requires a new run header or an approved header profile")
            else:
                result = self._parse_record(last, schemas, active_mode)
            yield self._count(result)
        if in_header:
            self._error(last, "MISSING_END_HEADER", "File ends before a complete header (or is empty)", fatal=True)
        self.report.complete = True

    def iter_text(self, content: str, *, source: str = "<memory>") -> Iterator[ParsedLine]:
        # StringIO's universal-newline handling avoids splitlines() treating a
        # vertical tab or Unicode separator inside a field as a physical line.
        with io.StringIO(content, newline="") as stream:
            yield from self.iter_lines(stream, source=source)

    def iter_file(self, path: str | os.PathLike[str], *, encoding: str = "utf-8") -> Iterator[ParsedLine]:
        """Hash exact bytes, parse from the same handle, and detect file mutation."""
        if self._used:
            raise RuntimeError("Create a new MacsParser for each file")
        path = Path(path)
        with path.open("rb") as binary:
            before = os.fstat(binary.fileno())
            digest = hashlib.sha256()
            for chunk in iter(lambda: binary.read(1024 * 1024), b""):
                digest.update(chunk)
            binary.seek(0)
            self.report.source_sha256 = digest.hexdigest()
            self.report.source_size_bytes = before.st_size
            self.report.encoding = encoding
            try:
                with io.TextIOWrapper(binary, encoding=encoding, errors="strict", newline="") as stream:
                    # Bound each read as well as the validation; an oversized
                    # physical line cannot force an unbounded readline allocation.
                    yield from self.iter_lines(iter(lambda: stream.readline(self.max_line_chars + 3), ""), source=str(path))
                    after = os.fstat(binary.fileno())
                    fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                    if fingerprint(before) != fingerprint(after):
                        self.report.complete = False
                        raise RuntimeError("Source file changed while being read; discard this parse and retry a closed snapshot")
            except BaseException:
                self.report.complete = False
                raise


class Record:
    """Compatibility table: original header names, explicit source positions."""

    def __init__(self, fields: Iterable[str], discriminator: str | None = None, *, session_index: int = 1):
        self.fields = list(_fields(fields))
        self.discriminator, self.session_index = discriminator, session_index
        self.entries: list[dict[str, Any]] = []
        self.parsed_rows: list[ParsedLine] = []

    @property
    def rows_count(self) -> int:
        return len(self.entries)

    @property
    def cols_count(self) -> int:
        return len(self.fields)

    def add_row(self, row: list[str]) -> None:
        if len(row) != self.cols_count:
            raise ValueError("Row dimension does not match the field dimension")
        self.entries.append(dict(zip(self.fields, row)))

    def to_table(self) -> dict[str, list[Any]]:
        return {field: [entry[field] for entry in self.entries] for field in self.fields}

    @property
    def table(self) -> dict[str, list[Any]]:
        return self.to_table()

    def to_dataframe(self):
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError("Install pandas only if to_dataframe() is needed") from exc
        return pd.DataFrame(self.entries, columns=self.fields)

    def __repr__(self) -> str:
        return f"Record(cols={self.cols_count}, rows={self.rows_count}, discriminator={self.discriminator!r}, session={self.session_index})"


class TemporaryRecordRegistry:
    def __init__(self):
        self.records: dict[str, Record] = {}

    def create_record(self, discriminator: str, fields: list[str]) -> None:
        if discriminator in self.records:
            raise ValueError(f"Schema already registered: {discriminator}")
        self.records[discriminator] = Record(fields, discriminator)

    def get_all_records(self) -> list[Record]:
        return list(self.records.values())

    def add_row(self, discriminator: str, row: list[str]) -> None:
        if discriminator not in self.records:
            raise ValueError(f"Unknown discriminator: {discriminator}")
        self.records[discriminator].add_row(row)

    def to_dict(self) -> dict[str, Any]:
        return {key: record.to_table() for key, record in self.records.items()}


class RecordCollection(list):
    """List-compatible result; audit_lines retains every line and its outcome."""

    def __init__(self, parser: MacsParser, lines: Iterable[ParsedLine]):
        super().__init__()
        self.audit_lines: list[ParsedLine] = []
        tables: dict[tuple[int, str], Record] = {}
        for line in lines:
            self.audit_lines.append(line)
            if line.kind != "record":
                continue
            schema = line.schema
            if schema is None or line.data is None:
                raise RuntimeError("Parser returned a record without schema/data")
            key = (line.session_index, schema.schema_sha256)
            if key not in tables:
                tables[key] = Record(schema.fields, schema.discriminator, session_index=line.session_index)
                self.append(tables[key])
            tables[key].entries.append(dict(line.data))
            tables[key].parsed_rows.append(line)
        self.report = parser.report.to_dict()


def parse_data(raw_content: str, delimiter: str = "\t", **options: Any) -> RecordCollection:
    """Legacy in-memory entry point; use MacsParser.iter_file for large files."""
    parser = MacsParser(delimiter=delimiter, **options)
    return RecordCollection(parser, parser.iter_text(raw_content))


def parse_data_from_file(file: str | os.PathLike[str], delimiter: str = "\t", *, encoding: str = "utf-8", **options: Any) -> dict[str, Any]:
    parser = MacsParser(delimiter=delimiter, **options)
    records = RecordCollection(parser, parser.iter_file(file, encoding=encoding))
    return {"name": file, "data": records, "report": records.report}


def export_file(path: str | os.PathLike[str], output: str | os.PathLike[str], *, encoding: str = "utf-8", **options: Any) -> dict[str, Any]:
    """Publish a completed audit directory; refuse to overwrite any output.

    Quarantine mode publishes rejects plus a non-success report. Fatal errors
    remove staging output. Existing input/output files are never overwritten.
    """
    destination = Path(output).absolute()
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    parser = MacsParser(**options)
    stage = Path(tempfile.mkdtemp(prefix=".macs-stage-", dir=destination.parent))
    try:
        with (stage / "records.jsonl").open("w", encoding="utf-8", newline="\n") as records, \
             (stage / "context.jsonl").open("w", encoding="utf-8", newline="\n") as context, \
             (stage / "rejects.jsonl").open("w", encoding="utf-8", newline="\n") as rejects:
            for line in parser.iter_file(path, encoding=encoding):
                target = records if line.kind == "record" else (rejects if line.kind == "rejected" else context)
                target.write(_json(line.to_dict()) + "\n")
        report = parser.report.to_dict()
        (stage / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        # Reserve the destination atomically. A racing existing destination is an
        # error; never replace it. report.json is moved last as the completion marker.
        destination.mkdir()
        try:
            for name in ("records.jsonl", "context.jsonl", "rejects.jsonl", "report.json"):
                os.replace(stage / name, destination / name)
        except BaseException:
            shutil.rmtree(destination)
            raise
        return report
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("input", type=Path)
    cli.add_argument("--output", required=True, type=Path, help="New audit directory (must not exist)")
    cli.add_argument("--quarantine", action="store_true", help="Preserve rejected records and finish the audit; exit code stays 2")
    cli.add_argument("--mode", choices=("auto", "single", "multiplex"), default="auto")
    cli.add_argument("--encoding", default="utf-8", help="Explicit source encoding; invalid bytes always fail")
    cli.add_argument("--profile", type=Path, help="Source-approved schema overrides, keyed by exact header fingerprint")
    args = cli.parse_args(argv)
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8")) if args.profile else None
        report = export_file(args.input, args.output, encoding=args.encoding, mode=args.mode,
                             quarantine=args.quarantine, profile=profile)
    except (OSError, ValueError, RuntimeError, LookupError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(_json({k: report[k] for k in ("success", "complete", "physical_lines", "counts", "all_data_lines_have_named_fields")}))
    return 0 if report["all_data_lines_have_named_fields"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
