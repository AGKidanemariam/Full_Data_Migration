import os
import pandas as pd
# from dotenv import load_dotenv
from ..macs_parser import Record
from sqlalchemy import (
    BIGINT,
    DOUBLE_PRECISION,
    INTEGER,
    TEXT,
    MetaData,
    Table,
    create_engine,
    inspect,
    insert,
    text,
)
from sqlalchemy.sql.sqltypes import DateTime

# load_dotenv(r"Z:\Gabriel\data_migration\.env")
#
# DATABASE_URL = os.getenv("DATABASE_URL")
#
# assert DATABASE_URL is not None, "Could load-in env variables"


class ORM:
    def __init__(self, database_url) -> None:
        self.database_url = database_url

    def initialize(self):
        self.engine = create_engine(self.database_url)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
        self.inspector = inspect(self.engine)

    def get_table_names(self):
        return self.inspector.get_table_names()

    def get_table_column_metadata(self, table_name: str) -> list[dict]:
        return self.inspector.get_columns(table_name)

    @staticmethod
    def _null_empty_values(df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert empty strings and whitespace-only strings to None/NA.

        Only string values are modified. Other values are left untouched.
        """
        df = df.copy()

        for column in df.columns:
            if pd.api.types.is_string_dtype(df[column]):
                df[column] = df[column].replace(r"^\s*$", pd.NA, regex=True)

        return df

    @staticmethod
    def _cast_column(series: pd.Series, col_type, column_name: str) -> pd.Series:
        """
        Cast a DataFrame column to a type compatible with the SQLAlchemy type.

        Invalid non-empty values raise an exception.
        Empty values should already have been converted to null.
        """

        if isinstance(col_type, TEXT):
            return series.astype("string")

        if isinstance(col_type, BIGINT):
            numeric = pd.to_numeric(series, errors="coerce")

            # An original non-null value becoming NaN means conversion failed.
            invalid = series.notna() & numeric.isna()

            if invalid.any():
                bad_values = series[invalid].tolist()
                raise ValueError(
                    f"Invalid BIGINT value(s) in column '{column_name}': {bad_values}"
                )

            return numeric.astype("Int64")

        if isinstance(col_type, INTEGER):
            numeric = pd.to_numeric(series, errors="coerce")

            invalid = series.notna() & numeric.isna()

            if invalid.any():
                bad_values = series[invalid].tolist()
                raise ValueError(
                    f"Invalid INTEGER value(s) in column '{column_name}': {bad_values}"
                )

            # Check that numeric values are actually integers.
            non_integer = numeric.notna() & (numeric % 1 != 0)

            if non_integer.any():
                bad_values = series[non_integer].tolist()
                raise ValueError(
                    f"Non-integer value(s) in INTEGER column "
                    f"'{column_name}': {bad_values}"
                )

            return numeric.astype("Int64")

        if isinstance(col_type, DOUBLE_PRECISION):
            numeric = pd.to_numeric(series, errors="coerce")

            invalid = series.notna() & numeric.isna()

            if invalid.any():
                bad_values = series[invalid].tolist()
                raise ValueError(
                    f"Invalid DOUBLE PRECISION value(s) in column "
                    f"'{column_name}': {bad_values}"
                )

            return numeric.astype("Float64")

        if isinstance(col_type, DateTime):
            # TODO:
            #
            # Determine:
            #   1. Whether source timestamps are seconds, milliseconds,
            #      microseconds, etc.
            #   2. Whether the PostgreSQL column is TIMESTAMP or
            #      TIMESTAMP WITH TIME ZONE.
            #   3. Whether source timestamps should be interpreted as UTC.
            #
            # For now, attempt normal pandas datetime parsing.
            return pd.to_datetime(
                series,
                errors="raise",
            )

        raise TypeError(
            f"Unsupported SQLAlchemy type for column '{column_name}': {col_type!r}"
        )

    def _prepare_dataframe(
        self,
        record: Record,
        table_name: str,
    ) -> pd.DataFrame:
        """
        Convert a Record into a DataFrame compatible with the database table.

        Responsibilities:
        - Convert the Record to a DataFrame.
        - Validate DataFrame/table column compatibility.
        - Convert empty strings to null.
        - Cast columns according to their SQLAlchemy types.
        - Raise on invalid non-empty values.
        """

        df = record.to_dataframe()
        col_metadata = self.get_table_column_metadata(table_name)

        table_columns = {col["name"]: col for col in col_metadata}

        dataframe_columns = set(df.columns)
        database_columns = set(table_columns)

        # Columns present in the DataFrame but absent from the DB schema
        # almost certainly indicate a schema mismatch.
        extra_columns = dataframe_columns - database_columns

        if extra_columns:
            raise ValueError(
                f"DataFrame contains columns not present in table "
                f"'{table_name}': {sorted(extra_columns)}"
            )

        # Columns missing from the DataFrame may be legitimate if the
        # database supplies a default value (including autoincrement IDs).
        missing_columns = database_columns - dataframe_columns

        for column_name in missing_columns:
            column = table_columns[column_name]

            has_default = (
                column.get("default") is not None
                or column.get("server_default") is not None
                or column.get("autoincrement") is True
            )

            if not has_default:
                raise ValueError(
                    f"DataFrame is missing required table column '{column_name}'"
                )

        # Empty strings / whitespace-only strings become null.
        df = self._null_empty_values(df)

        # Cast every DataFrame column according to the database schema.
        for column_name in df.columns:
            col_type = table_columns[column_name]["type"]

            df[column_name] = self._cast_column(
                df[column_name],
                col_type,
                column_name,
            )

        return df

    def push_to_table(
        self,
        table_name: str,
        record: Record,
        batch_size: int = 1000,
    ):
        """
        Prepare a Record and bulk insert it into a database table.

        The entire operation is performed in one transaction. If any
        batch fails, the transaction is rolled back.
        """

        df = self._prepare_dataframe(record, table_name)

        if df.empty:
            return 0

        table = Table(
            table_name,
            self.metadata,
            autoload_with=self.engine,
        )

        # Convert pandas' NA/NaT values to Python None so SQLAlchemy
        # sends them as SQL NULL.
        records = df.astype(object).where(pd.notna(df), None).to_dict(
            orient="records"
        )

        inserted = 0

        with self.engine.begin() as conn:
            for start in range(0, len(records), batch_size):
                batch = records[start : start + batch_size]

                conn.execute(
                    insert(table),
                    batch,
                )

                inserted += len(batch)

        return inserted

    def drop_table(self, table_name):
        table = Table(table_name, autoload_with=self.engine)
        table.drop(self.engine, checkfirst=True)

    def execute_sql_file(self, file_name: str):
        with open(file_name, "r") as file:
            content = file.read()

        with self.engine.connect() as conn, conn.begin():
            statements = content.split(";")

            for statement in statements:
                clean_statement = statement.strip()

                if clean_statement:
                    conn.execute(text(clean_statement))


def main():
    orm = ORM(DATABASE_URL)
    orm.setup_engine()

    input_file = "sql/tables/flight_state.sql"

    orm.execute_sql_file(input_file)

    table_names = orm.get_table_names()

    print(table_names)

    try:
        table = Table("flight_state_telemetry", orm.metadata, autoload_with=orm.engine)
        table.drop(orm.engine, checkfirst=True)
        print(f"Dropped {table} successfully")
    except Exception as e:
        print(e)
    finally:
        print("Done executing.")


if __name__ == "__main__":
    orm = ORM(DATABASE_URL)
    orm.initialize()
    res = orm.get_table_column_metadata("flight_state")
    res = orm._prepare_record(Record([]), "flight_state")
