"""
Developer utility for inspecting parsed MACS documents.

Usage
-----
python -m scripts.inspect_parsed_macs "<file_path>" "<macs_family>"

Example
-------
python -m scripts.inspect_parsed_macs \
"data/extracted/example/example" \
"FlightState"
"""

from pathlib import Path
from pprint import pprint
import argparse

from src.inspection.parsers.macs_parser import MacsParser


PREVIEW_ROW_COUNT = 5


def print_divider(
    title: str,
) -> None:
    """
    Print a readable section divider.
    """

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_metadata(
    metadata: dict,
) -> None:
    """
    Print parsed document metadata.
    """

    print_divider(
        "METADATA"
    )

    if not metadata:

        print(
            "No metadata found."
        )

        return

    for key, value in metadata.items():

        print(
            f"{key}: {value}"
        )


def print_section_summary(
    document,
) -> None:
    """
    Print a summary of all parsed sections.
    """

    print_divider(
        "SECTION SUMMARY"
    )

    print(
        f"Section count: {document.section_count}"
    )

    for index, section in enumerate(
        document.sections,
        start=1,
    ):

        print()
        print(
            f"{index}. {section.name}"
        )

        print(
            f"   Columns: {section.column_count}"
        )

        print(
            f"   Rows: {section.row_count}"
        )


def row_as_dictionary(
    section,
    row: list[str],
) -> dict[str, str | None]:
    """
    Match one parsed row to its header.

    Missing fields are represented as None.
    Extra fields are preserved separately.
    """

    record: dict[str, str | None] = {}

    for index, column_name in enumerate(
        section.header
    ):

        if index < len(row):

            record[column_name] = row[index]

        else:

            record[column_name] = None

    if len(row) > len(section.header):

        record[
            "__extra_fields__"
        ] = row[
            len(section.header):
        ]

    return record


def print_section_details(
    section,
) -> None:
    """
    Print the header and sample records
    for one parsed MACS section.
    """

    print_divider(
        f"SECTION: {section.name}"
    )

    print(
        f"Column count: {section.column_count}"
    )

    print(
        f"Row count: {section.row_count}"
    )

    print()

    print(
        "HEADER:"
    )

    for index, column in enumerate(
        section.header,
        start=1,
    ):

        print(
            f"{index:>3}. {column}"
        )

    if not section.rows:

        print()
        print(
            "No data rows found."
        )

        return

    first_rows = section.rows[
        :PREVIEW_ROW_COUNT
    ]

    last_rows = section.rows[
        -PREVIEW_ROW_COUNT:
    ]

    print_divider(
        f"FIRST {len(first_rows)} ROW(S) — {section.name}"
    )

    for index, row in enumerate(
        first_rows,
        start=1,
    ):

        print()
        print(
            f"ROW {index}"
        )

        print(
            f"Fields in row: {len(row)}"
        )

        pprint(
            row_as_dictionary(
                section,
                row,
            ),
            sort_dicts=False,
        )

    print_divider(
        f"LAST {len(last_rows)} ROW(S) — {section.name}"
    )

    start_number = (
        section.row_count
        - len(last_rows)
        + 1
    )

    for offset, row in enumerate(
        last_rows
    ):

        actual_row_number = (
            start_number
            + offset
        )

        print()
        print(
            f"ROW {actual_row_number}"
        )

        print(
            f"Fields in row: {len(row)}"
        )

        pprint(
            row_as_dictionary(
                section,
                row,
            ),
            sort_dicts=False,
        )


def print_row_length_analysis(
    section,
) -> None:
    """
    Compare row field counts against
    the section header length.
    """

    print_divider(
        f"ROW LENGTH CHECK: {section.name}"
    )

    expected = section.column_count

    matching = 0

    shorter = 0

    longer = 0

    mismatches: list[
        tuple[int, int]
    ] = []

    for row_number, row in enumerate(
        section.rows,
        start=1,
    ):

        actual = len(row)

        if actual == expected:

            matching += 1

        elif actual < expected:

            shorter += 1

            mismatches.append(
                (
                    row_number,
                    actual,
                )
            )

        else:

            longer += 1

            mismatches.append(
                (
                    row_number,
                    actual,
                )
            )

    print(
        f"Expected fields per row: {expected}"
    )

    print(
        f"Rows matching header: {matching}"
    )

    print(
        f"Rows shorter than header: {shorter}"
    )

    print(
        f"Rows longer than header: {longer}"
    )

    if mismatches:

        print()
        print(
            "First 10 mismatches:"
        )

        for row_number, actual in mismatches[:10]:

            print(
                (
                    f"Row {row_number}: "
                    f"{actual} field(s)"
                )
            )

    else:

        print()
        print(
            "All rows match the header length."
        )


def inspect_document(
    file_path: Path,
    macs_family: str,
) -> None:
    """
    Parse and print a complete MACS document preview.
    """

    parser = MacsParser()

    document = parser.parse(
        file_path,
        macs_family,
    )

    print_divider(
        "MACS PARSER INSPECTION"
    )

    print(
        f"File: {document.file_name}"
    )

    print(
        f"Path: {document.file_path}"
    )

    print(
        f"MACS family: {document.macs_family}"
    )

    print_metadata(
        document.metadata,
    )

    print_section_summary(
        document,
    )

    for section in document.sections:

        print_section_details(
            section,
        )

        print_row_length_analysis(
            section,
        )

    print_divider(
        "WARNINGS"
    )

    if document.warnings:

        for warning in document.warnings:

            print(
                f"- {warning}"
            )

    else:

        print(
            "No parser warnings."
        )

    print_divider(
        "INSPECTION COMPLETE"
    )


def main() -> None:
    """
    Command-line entry point.
    """

    argument_parser = argparse.ArgumentParser(
        description=(
            "Parse and inspect a MACS source file."
        )
    )

    argument_parser.add_argument(
        "file_path",
        type=Path,
        help=(
            "Path to the MACS source file."
        ),
    )

    argument_parser.add_argument(
        "macs_family",
        type=str,
        help=(
            "MACS family such as FlightState, "
            "Trajectory, CompMet, Pilot, ATC, "
            "or Workload."
        ),
    )

    arguments = (
        argument_parser.parse_args()
    )

    if not arguments.file_path.exists():

        raise FileNotFoundError(
            (
                "MACS source file does not exist: "
                f"{arguments.file_path}"
            )
        )

    inspect_document(
        file_path=arguments.file_path,
        macs_family=arguments.macs_family,
    )


if __name__ == "__main__":
    main()