"""
Miscellaneous functions
"""

import os
import re
import pandas as pd
from datetime import datetime


def read(file: str) -> str:
    """
    Reads a file from disk, given the path to the file.
    Returns the raw string content from such file.

    :param str file: The path to file to read from
    """
    with open(file, "r") as f:
        return f.read()


def preprocess_lines(lines: list[str], delimiter: str) -> list[str]:
    """
    Given the content lines of a log file and it's delimiter,
    for every line, it will get rid of any redundant spaces
    following a delimiter instance.

    :param list[str] lines: The content lines of a log file
    :param str   delimiter: The delimiter which separates values

    returns the new preprocessed content lines
    """
    # getting rid of the redundant spaces after \t's
    line_buffer = []
    prev = None

    old = f"{delimiter} "
    new = delimiter

    for line in lines:
        if line.strip() == "":
            continue

        new_line = line.replace(old, new)
        line_buffer.append(new_line)

    return line_buffer


def find_str_indexes(lines: list[str], patterns: list[str]) -> list[int]:
    """
    Given the lines of a log file, and a few patterns
    to check for, it will perform a singular scan
    collecting the line indexes for any patterns found,
    a pattern being the prefix string of a line. For every ith
    integer of the result array, it will correspond to the
    line index of where the ith pattern matched. If a pattern is not
    matched, then the ith result for the ith pattern
    will be -1.

    :param list[str]    lines: The content lines of a log file
    :param list[str] patterns: The prefix string instances to look for
    """
    idxes = {pattern: -1 for pattern in patterns}

    for i, line in enumerate(lines):
        for key in idxes:
            if idxes[key] == -1 and line.startswith(key):
                idxes[key] = i
                break

    # returning indexes in order given
    return [idxes[pattern] for pattern in patterns]


def _sanitize_string(value: str) -> str:
    """
    Helper function to normalize string values

    :param str value: The string value to normalize
    """
    value = value.replace(" ", "_")
    value = value.replace("__", "_")
    value = value.replace("-", "_")
    return value


def _camel_case_to_snake_case(value: str) -> str:
    """
    Converts camel case strings or upper case strings into
    lower snake case strings given string value

    :param str value: The string to convert to snake case
    """
    if not value:
        return value

    value = _sanitize_string(value)

    result = []
    length = len(value)

    for i, char in enumerate(value):
        if char.isupper():
            # Add separator when transitioning into an uppercase word.
            if i > 0 and (
                value[i - 1].islower() or (i + 1 < length and value[i + 1].islower())
            ):
                result.append("_")

            result.append(char.lower())
        else:
            result.append(char)

    return "".join(result)


def normalize_column_names(record: Record, mapping: dict[str, str]) -> None:
    """
    Normalize column names in a Record by applying a custom mapping and converting to snake_case.

    This function remaps the column names of a log file record for better consistency and
    readability. It applies a user-provided mapping dictionary first, then falls back to
    converting camelCase names to snake_case for any unmapped columns.

    :param Record          record: The record object whose column names will be normalized. The record
                                   is modified in-place, with both its `fields` list and `table` dictionary updated.
    :param dict[str, str] mapping: A dictionary mapping original column names to their desired
                                   normalized names. If a column name is not in this mapping, it will be automatically
                                   converted from camelCase to snake_case.

    Returns:
        None: The function modifies the record in-place and does not return a value.

    Raises:
        ValueError: If two or more original column names map to the same normalized name,
            indicating a collision that would result in data loss.

    Note:
        - The original field order is preserved in the normalized record.
        - All modifications are made in-place to avoid unnecessary memory allocation.
        - Column name collisions are detected and prevented to ensure data integrity.
    """
    new_fields = []

    for field in record.fields:
        new_name = mapping.get(field, _camel_case_to_snake_case(field))

        if new_name in new_fields:
            raise ValueError(f"Column name collision: '{field}' -> '{new_name}'")

        new_fields.append(new_name)

    record.fields[:] = new_fields


def extract_timestamp(line: str) -> datetime:
    match = re.search(r'\b(\d{2}:\d{2}:\d{2})\b', line)

    if not match:
        raise ValueError(f"No timestamp found in: {line!r}")

    return datetime.strptime(match.group(1), "%H:%M:%S")
