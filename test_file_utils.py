from pathlib import Path

from src.common.file_utils import (
    move_file_safe,
)

test_source = Path("sample.txt")

test_source.write_text("Hello World!")

destination = move_file_safe(
    test_source,
    Path("metadata"),
)

print(destination)

