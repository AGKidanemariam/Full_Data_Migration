"""
field_mapper.py
================

One-stop script for the ETL field-mapping step. Combines everything
discussed:

  1. SQL SCHEMA PARSING
     Reads CREATE TABLE DDL (sql_schema_relational.sql, sql_schema_timeseries.sql,
     ...) into {table: {column: ColumnInfo(type, nullable, primary_key)}}.

  2. TABLE AUTO-DETECTION
     Since your only input is a list of record field names (no table name,
     no discriminator), `guess_table()` scores every table in the schema by
     how well its columns match your field names and returns the best
     candidate(s).

  3. FUZZY FIELD -> COLUMN MATCHING
     Exact matches (case/whitespace/punctuation-insensitive) resolve
     automatically. Everything else gets scored against that table's
     columns by Levenshtein distance; the top 5 are handed to a `resolver`
     callback (your UI) to pick the correct one, or skip.

  4. CACHING
     Every resolved answer (field->column, and table guesses if you choose
     to persist those too) is cached to disk so you're never asked the same
     question twice across files/runs.

  5. OUTPUT
     `generate_field_mapping(...)` returns exactly:

         {
             "<original_record_field_name>": {
                 "sql_column": "<matched_sql_column_name>" | None,
                 "type":       "<sql_type>" | None,
                 "nullable":   True | False | None,
             },
             ...
         }

MINIMAL USAGE (only record field names, nothing else known):

    from field_mapper import load_schema_from_files, generate_field_mapping, cli_resolver

    schema = load_schema_from_files([
        "sql_schema_relational.sql",
        "sql_schema_timeseries.sql",
    ])

    field_names = ["UTC_TIME", "WEIGHT", "FUEL_RATE", "CALLSIGN", "ALT", ...]

    mapping = generate_field_mapping(
        field_names,
        schema,
        table_name=None,       # <- unknown; auto-detected from field_names
        resolver=cli_resolver, # <- swap for your own UI callback
    )
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# ============================================================================
# 1. SQL SCHEMA PARSING
# ============================================================================

_STOP_KEYWORDS = re.compile(
    r"\b(NOT\s+NULL|NULL|DEFAULT|REFERENCES|UNIQUE|PRIMARY\s+KEY|CHECK|"
    r"CONSTRAINT|GENERATED)\b",
    re.IGNORECASE,
)

_TABLE_CONSTRAINT_KEYWORDS = {
    "CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "EXCLUDE", "LIKE",
}


@dataclass
class ColumnInfo:
    name: str
    sql_type: str
    nullable: bool
    is_primary_key: bool = False

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "type": self.sql_type,
            "nullable": self.nullable,
            "primary_key": self.is_primary_key,
        }


SchemaDict = Dict[str, Dict[str, ColumnInfo]]


def _strip_line_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


def _extract_create_table_blocks(sql_text: str) -> List[Tuple[str, str]]:
    """Find every CREATE TABLE [IF NOT EXISTS] name (...) block, using
    paren-depth counting (not regex) so nested parens - GEOMETRY(POLYGON, 4326),
    inline REFERENCES(...)/CHECK(...) - don't break the match."""
    blocks: List[Tuple[str, str]] = []
    header_re = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?(\w+)\"?\s*\(",
        re.IGNORECASE,
    )
    for m in header_re.finditer(sql_text):
        table_name = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(sql_text) and depth > 0:
            if sql_text[i] == "(":
                depth += 1
            elif sql_text[i] == ")":
                depth -= 1
            i += 1
        body = sql_text[start : i - 1]
        blocks.append((table_name, body))
    return blocks


def _split_top_level(text: str, sep: str = ",") -> List[str]:
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        parts.append("".join(current))
    return parts


def _parse_column_def(part: str) -> Optional[ColumnInfo]:
    collapsed = " ".join(part.split())
    if not collapsed:
        return None

    m = re.match(r'^"?(\w+)"?\s+(.*)$', collapsed)
    if not m:
        return None
    name, rest = m.groups()

    if name.upper() in _TABLE_CONSTRAINT_KEYWORDS:
        return None

    stop = _STOP_KEYWORDS.search(rest)
    sql_type = (rest[: stop.start()] if stop else rest).strip().rstrip(",")

    is_pk = bool(re.search(r"\bPRIMARY\s+KEY\b", rest, re.IGNORECASE))
    not_null = bool(re.search(r"\bNOT\s+NULL\b", rest, re.IGNORECASE))
    nullable = not (not_null or is_pk)

    return ColumnInfo(name=name, sql_type=sql_type, nullable=nullable, is_primary_key=is_pk)


def parse_sql_schema(sql_text: str) -> SchemaDict:
    """Parse CREATE TABLE statements from raw SQL text.
    Returns {table_name: {column_name: ColumnInfo}}."""
    schema: SchemaDict = {}
    for table_name, raw_body in _extract_create_table_blocks(sql_text):
        body = _strip_line_comments(raw_body)
        columns: Dict[str, ColumnInfo] = {}
        for chunk in _split_top_level(body):
            col = _parse_column_def(chunk)
            if col is not None:
                columns[col.name] = col
        schema[table_name] = columns
    return schema


def load_schema_from_files(paths: List[str]) -> SchemaDict:
    """Parse and merge schema from one or more .sql files."""
    merged: SchemaDict = {}
    for p in paths:
        text = Path(p).read_text(encoding="utf-8")
        merged.update(parse_sql_schema(text))
    return merged


# ============================================================================
# 2. LEVENSHTEIN MATCHING (columns are always scoped to a single table)
# ============================================================================

def normalize(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    return name


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    previous_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current_row = [i]
        for j, cb in enumerate(b, 1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (ca != cb)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def find_best_matches(
    field_name: str, sql_columns: List[str], top_n: int = 5
) -> List[Tuple[str, int]]:
    """Closest `top_n` SQL columns to `field_name`, within ONE table's
    column list. Never pool columns across tables - see guess_table() below
    for cross-table comparison."""
    norm_field = normalize(field_name)
    scored = [(col, levenshtein(norm_field, normalize(col))) for col in sql_columns]
    scored.sort(key=lambda pair: (pair[1], pair[0]))
    return scored[:top_n]


# ============================================================================
# 3. TABLE AUTO-DETECTION
# Only needed because the only input available is a bare list of field
# names, with no table name or discriminator attached.
# ============================================================================

def guess_table(
    record_columns: List[str], schema: SchemaDict, top_n: int = 3
) -> List[Tuple[str, float]]:
    """
    Score every table by how well its columns explain `record_columns`,
    and return the best `top_n` candidates as (table_name, avg_distance)
    sorted best-first (lower avg_distance = better fit).

    For each table: for every record field, find its single closest
    column in that table (Levenshtein) and average those distances. The
    table with the lowest average is the best overall fit.
    """
    scores: List[Tuple[str, float]] = []
    for table, cols in schema.items():
        col_names = list(cols.keys())
        if not col_names or not record_columns:
            scores.append((table, float("inf")))
            continue
        total = sum(find_best_matches(f, col_names, top_n=1)[0][1] for f in record_columns)
        scores.append((table, total / len(record_columns)))
    scores.sort(key=lambda pair: pair[1])
    return scores[:top_n]


# ============================================================================
# 4. CACHING
# ============================================================================

SKIP_SENTINEL = "__SKIP__"

Resolver = Callable[[str, List[Tuple[str, int]]], Optional[str]]
TableResolver = Callable[[List[Tuple[str, float]]], str]


class MappingCache:
    """Persists resolved field->column choices (and deliberate skips) to
    disk, keyed by table + normalized field name, so the same question is
    never asked twice across files/runs."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else None
        self._data: Dict[str, str] = {}
        if self.path and self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def key(self, table_name: str, field_name: str) -> str:
        return f"{table_name}::{normalize(field_name)}"

    def get(self, table_name: str, field_name: str) -> Optional[str]:
        raw = self._data.get(self.key(table_name, field_name))
        if raw is None:
            return None
        return None if raw == SKIP_SENTINEL else raw

    def has(self, table_name: str, field_name: str) -> bool:
        return self.key(table_name, field_name) in self._data

    def set(self, table_name: str, field_name: str, chosen_column: Optional[str]) -> None:
        self._data[self.key(table_name, field_name)] = chosen_column or SKIP_SENTINEL

    def save(self) -> None:
        if self.path:
            self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")


def resolve_field(
    field_name: str,
    sql_columns: List[str],
    table_name: str,
    resolver: Resolver,
    cache: Optional[MappingCache] = None,
    top_n: int = 5,
) -> Optional[str]:
    """Resolve one field name to a SQL column within one table:
    cache hit -> exact match -> Levenshtein top-N handed to `resolver`."""
    if cache is not None and cache.has(table_name, field_name):
        return cache.get(table_name, field_name)

    exact_lookup = {normalize(c): c for c in sql_columns}
    norm_field = normalize(field_name)
    if norm_field in exact_lookup:
        chosen = exact_lookup[norm_field]
        if cache is not None:
            cache.set(table_name, field_name, chosen)
        return chosen

    candidates = find_best_matches(field_name, sql_columns, top_n=top_n)
    chosen = resolver(field_name, candidates)
    if cache is not None:
        cache.set(table_name, field_name, chosen)
    return chosen


# ============================================================================
# 5. FINAL MAPPING GENERATION  (the function you actually call)
# ============================================================================

FieldMapping = Dict[str, Dict[str, Optional[object]]]


def generate_field_mapping(
    record_columns: List[str],
    schema: SchemaDict,
    table_name: Optional[str] = None,
    resolver: Resolver = None,  # type: ignore[assignment]
    cache: Optional[MappingCache] = None,
    top_n: int = 5,
    table_resolver: Optional[TableResolver] = None,
) -> FieldMapping:
    """
    Build {original_field_name: {sql_column, type, nullable}} from nothing
    but `record_columns` (a bare list of field-name strings) and `schema`.

    table_name : if you already know the target table, pass it and
                 auto-detection is skipped. If None, guess_table() picks
                 the best-fitting table automatically - or, if you supply
                 `table_resolver`, that callback gets the ranked guesses
                 and returns the table name your UI confirmed.
    resolver    : required. Your UI callback for ambiguous fields, see
                  cli_resolver() below for the expected signature.
    """
    if resolver is None:
        raise ValueError("resolver is required (see cli_resolver for the expected signature)")

    if table_name is None:
        guesses = guess_table(record_columns, schema)
        if not guesses:
            raise ValueError("No tables found in schema.")
        table_name = table_resolver(guesses) if table_resolver else guesses[0][0]

    if table_name not in schema:
        raise KeyError(
            f"Table '{table_name}' not found in schema. "
            f"Available tables: {sorted(schema.keys())}"
        )

    table_columns = schema[table_name]
    sql_column_names = list(table_columns.keys())

    mapping: FieldMapping = {}
    for field_name in record_columns:
        matched_column = resolve_field(
            field_name, sql_column_names, table_name, resolver, cache=cache, top_n=top_n
        )
        if matched_column is not None:
            col_info = table_columns[matched_column]
            mapping[field_name] = {
                "sql_column": col_info.name,
                "type": col_info.sql_type,
                "nullable": col_info.nullable,
            }
        else:
            mapping[field_name] = {"sql_column": None, "type": None, "nullable": None}

    return mapping


def save_field_mapping(mapping: FieldMapping, path: str) -> None:
    Path(path).write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")


def load_field_mapping(path: str) -> FieldMapping:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ============================================================================
# 6. STAND-ALONE RESOLVERS (swap these out for your own UI)
# ============================================================================

def cli_resolver(field_name: str, candidates: List[Tuple[str, int]]) -> Optional[str]:
    print(f"\nNo exact SQL column match for parsed field: '{field_name}'")
    for i, (col, dist) in enumerate(candidates, 1):
        print(f"  [{i}] {col}   (distance={dist})")
    print("  [0] -- skip this field --")
    while True:
        choice = input("Choose column number: ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1][0]
        print("Invalid choice, try again.")


def cli_table_resolver(guesses: List[Tuple[str, float]]) -> str:
    print("\nCould not determine target table with certainty. Best guesses:")
    for i, (table, score) in enumerate(guesses, 1):
        print(f"  [{i}] {table}   (avg distance={score:.2f})")
    while True:
        choice = input("Choose table number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(guesses):
            return guesses[int(choice) - 1][0]
        print("Invalid choice, try again.")


# ============================================================================
# 7. CLI DEMO
# ============================================================================

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generate a {record_field: {sql_column, type, nullable}} "
                     "mapping from just a list of record field names."
    )
    parser.add_argument("schema_files", nargs="+", help="One or more .sql DDL files.")
    parser.add_argument(
        "--fields", nargs="+", required=True,
        help="Record field names to map, e.g. --fields UTC_TIME WEIGHT CALLSIGN ALT",
    )
    parser.add_argument(
        "--table", default=None,
        help="Target table name. If omitted, it is auto-detected from --fields.",
    )
    parser.add_argument("--cache", default="mapping_cache.json")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    schema = load_schema_from_files(args.schema_files)
    cache = MappingCache(args.cache)

    mapping = generate_field_mapping(
        args.fields,
        schema,
        table_name=args.table,
        resolver=cli_resolver,
        cache=cache,
        table_resolver=cli_table_resolver,
    )
    cache.save()

    print("\nFinal mapping:")
    print(json.dumps(mapping, indent=2, sort_keys=True))

    if args.out:
        save_field_mapping(mapping, args.out)
        print(f"\nSaved mapping to {args.out}", file=sys.stderr)
