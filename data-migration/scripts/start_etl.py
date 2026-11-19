"""
Main entry point file that starts the program
"""
from data_migration.macs_parser import mappings
from data_migration.macs_parser.macs_parser import parse_data, parse_data_from_file


LOG_FILE_DIRECTORY_LOC = "" # directory to where log files get outputted

READ_RATE_PER_SEC = 1


def main():
    ...

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit()
    except Exception as e:
        print(f"Error: {e}")
