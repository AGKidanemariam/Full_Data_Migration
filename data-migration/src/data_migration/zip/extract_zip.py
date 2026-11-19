import zipfile
from pathlib import Path

zip_folder = Path("raw_zips")
extract_folder = Path("extracted")
extract_folder.mkdir(exist_ok=True)

for zip_file in zip_folder.glob("*.zip"):
    output_path = extract_folder / zip_file.stem
    output_path.mkdir(exist_ok=True)

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(output_path)

    print(f"Extracted: {zip_file.name}")
