from pathlib import Path
import pandas as pd

for file in Path("extracted").rglob("*"):
    if file.is_file():
        print(file)

        if file.suffix.lower() == ".csv":
            df = pd.read_csv(file, nrows=5)
            print(df.columns)
            print(df.head())
