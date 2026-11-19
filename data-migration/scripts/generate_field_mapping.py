import re
import sys
import time
from load_logs import load_logs, File

sys.path.insert(0, "..")
from data_migration.macs_parser.main import main as process_log_files


SQL_FILE = "../../../DATA/MACS Sample SQL Schema/sql_schema_relational.sql"

DIR = "../../Log Files/Logs"

def read(file: str) -> str:
    with open(file, "r") as f:
        return f.read()


def levenshtein_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a

    previous = list(range(len(b) + 1))

    for i, char_a in enumerate(a, 1):
        current = [i]

        for j, char_b in enumerate(b, 1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (char_a != char_b)

            current.append(min(insert, delete, replace))

        previous = current

    return previous[-1]


def top_matches(sample: str, available_strings: list[str], n: int = 5) -> list[str]:
    distances = [
        (levenshtein_distance(sample, candidate), candidate)
        for candidate in available_strings
    ]

    distances.sort(key=lambda x: x[0])

    return [candidate for _, candidate in distances[:n]]


def camel_case_to_snake_case(string: str):
    buffer = []

    for i, char in enumerate(string):
        if char.isupper():
            if i > 0:
                buffer.append("_")
            buffer.append(char.lower())
            continue
        buffer.append(char)

    return "".join(buffer)



def extract_sql_fields(sql: str) -> dict[str, list[str]]:
    tables = {}

    table_pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL
    )

    for table_match in table_pattern.finditer(sql):
        table_name = table_match.group(1)
        table_body = table_match.group(2)

        fields = []

        for line in table_body.splitlines():
            line = line.strip()

            if not line or line.startswith("--"):
                continue

            # Ignore table-level constraints
            if re.match(
                r"(CONSTRAINT|PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK)\b",
                line,
                re.IGNORECASE
            ):
                continue

            field = line.split()[0].rstrip(",")

            fields.append(field)

        tables[table_name] = fields

    return tables


def extract_all_log_file_field_names():
    print("Loading logs...")
    start = time.time()
    # logs = load_logs()
    res = process_log_files(k=100, dir="../Log Files/Logs")

    records, errors = res

    print(records)
    exit()

    print(f"Finished loading logs into memory in: {time.time() - start} seconds")

    print("Extracting field names")
    field_names = set()

    for rec in records:
        recs = rec["data"]
        for record in recs:
            print(record)

    return field_names


def main(logs: list[File] = []):
    content = read(SQL_FILE)

    res = extract_sql_fields(content)

    for name, fields in res.items():
        print(name, fields)

if __name__ == "__main__":
    # logs = load_logs()
    # main(logs)
    # main()
    field_names = extract_all_log_file_field_names()
    print(field_names)
