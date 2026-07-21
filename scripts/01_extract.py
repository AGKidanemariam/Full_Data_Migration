"""
Entry point for the extraction stage.

Run this script to process incoming ZIP files.
"""

from src.extraction.zip_processor import process_all_zip_files


def main() -> None:
    """
    Start the extraction stage.
    """

    process_all_zip_files()


if __name__ == "__main__":
    main()

