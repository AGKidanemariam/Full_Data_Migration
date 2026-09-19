from pathlib import Path

from src.inspection.parsers.macs_parser import MacsParser
from src.transformation.family.flightstate_transformer import FlightStateTransformer


def main():
    file_path = input("Enter FlightState file path: ").strip().strip('"')

    # Convert the entered path from a string to a Path object
    file_path = Path(file_path)


    # Parse the original MACS FlightState file
    parser = MacsParser()
    document = parser.parse(file_path, "FlightState")

    # Make sure a section was parsed
    if not document.sections:
        print("No sections were parsed.")
        return

    section = document.sections[0]

    # Make sure the section contains records
    if not section.records:
        print("No FlightState records were parsed.")
        return

    # Get the first real parsed FlightState record
    original_row = section.records[0]

    # Transform the record
    transformer = FlightStateTransformer()

    transformed_row = transformer.transform_row(
        original_row,
        source_line_number=1,
    )

    print("\n--- ORIGINAL PARSED ROW ---")

    for key, value in original_row.items():
        print(f"{key}: {value}")

    print("\n--- TRANSFORMED ROW ---")

    for key, value in transformed_row.items():
        print(
            f"{key}: {value} "
            f"({type(value).__name__})"
        )


if __name__ == "__main__":
    main()
