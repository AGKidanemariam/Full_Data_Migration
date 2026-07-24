"""
Entry point for the inspection stage.
"""

from src.inspection.inspector import inspect_all_files


def main() -> None:
    """
    Run the inspection stage.
    """

    inspect_all_files()


if __name__ == "__main__":
    main()