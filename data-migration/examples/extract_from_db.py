"""
A sample trying to get the data from a random table
"""
import sqlite3 as sql


SAMPLE_DB_LOC = r"Z:\Gabriel\sample.db"


def get_random_table(cursor) -> str:
    cursor.execute(
        "SELECT name FROM sqlite_schema WHERE type=\"table\" AND name NOT LIKE \"sqlite_%\""
    )

    table_names: list[tuple[str]] = cursor.fetchall()

    return table_names[0][0]


def get_column_names(cursor, table_name) -> list[str]:
    cursor.execute(f"SELECT * FROM \"{table_name}\" LIMIT 0")
    col_names = [desc[0] for desc in cursor.description]

    return col_names


def get_rows(cursor, table_name) -> list[tuple[str, ...]]:
    cursor.execute(f"SELECT * FROM \"{table_name}\"")

    rows: list[tuple[str, ...]] = cursor.fetchall()

    return rows


if __name__ == "__main__":
    conn = sql.connect(SAMPLE_DB_LOC)
    cursor = conn.cursor()

    table = get_random_table(cursor)
    col_names = get_column_names(cursor, table)
    rows = get_rows(cursor, table)

    print(col_names, "\n")
    print(rows)
