from pathlib import Path

from src.common.hash_utils import calculate_sha256

sample = Path("sample.txt")

sample.write_text("Hello World!!")

print(calculate_sha256(sample))