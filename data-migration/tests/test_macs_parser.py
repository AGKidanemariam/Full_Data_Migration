import pandas as pd
from data_migration.macs_parser import Record, TemporaryRecordRegistry


def test_record_entries_initialization():
    record = Record(["a", "b"])
    record.add_row([1, 2])
    record.add_row([3, 4])

    assert record.entries == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_record_entries_to_table():
    record = Record(["a", "b"])

    record.add_row([1, 2])
    record.add_row([3, 4])

    expected_res = {"a": [1, 3], "b": [2, 4]}

    assert record.to_table() == expected_res


def test_record_to_dataframe():
    record = Record(["a", "b"])

    record.add_row([1, 2])
    record.add_row([3, 4])

    expected_res = pd.DataFrame(
        {
            "a": [1, 3],
            "b": [2, 4],
        }
    )

    assert record.to_dataframe().equals(expected_res)


def test_temp_record_registry_record_creation():
    registry = TemporaryRecordRegistry()

    column_names = ["col 1", "col 2"]
    discriminator = None

    registry.create_record(discriminator, column_names)

    assert len(registry.records) == 1
    assert registry.records[discriminator].fields == column_names


def test_temp_record_registry_record_row_addition():
    registry = TemporaryRecordRegistry()

    column_names = ["col 1", "col 2"]
    discriminator = None

    registry.create_record(discriminator, column_names)

    registry.add_row(discriminator, [1, 2])

    record = registry.records[discriminator]
    print(record.entries)
    
    assert len(record.entries) == 1
    # Reason why I'm using the "col_1" key
    # as opposed to "col 1", like seen in the 
    # initialization step, it's because whenever
    # a record is initialized, it runs a function
    # called `normalize_column_names()` on the column names,
    # which transforms the column name to a lowercase snake case format
    assert record.entries[0]["col_1"] == 1 and record.entries[0]["col_2"] == 2
