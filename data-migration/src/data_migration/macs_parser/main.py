import os
import json
import random
import pandas as pd
import sqlite3 as sql
from tqdm import tqdm
from threading import Thread

from . import parse_data_from_file
from . import read

# DIR = "./Log Files/Logs"
DIR = r"Z:\Gabriel\Log Files\Logs"
DELIMITER = "\t"


def process_log(log_file, records, errors):
    """
    Helper function for mulithreading
    """
    try:
        data = parse_data_from_file(log_file, DELIMITER)
        records.append(data)
    except Exception as e:
        errors.update(
            {log_file: {"name": log_file, "diagnosis": f"{type(e).__name__}: {e}"}}
        )


def process_chunk(chunk, records, errors):
    """
    Helper function to deal with chunks of data in parallel
    """
    for log in tqdm(chunk):
        process_log(log, records, errors)


def migrate_to_db(records, errors):
    """
    Test function for migration
    """
    conn = sql.connect("sample.db")

    for i in range(len(records)):
        obj = records[i]
        name = obj["name"].rsplit(".", 1)[0]
        try:
            df = pd.DataFrame(records[i]["data"])
            df.to_sql(name=name, con=conn, if_exists="append")
        except Exception as e:
            errors.update({name: {"name": name, "diagnosis": e}})

    conn.close()


def main(*, k=-1, dir=DIR):
    """
    Main entry point of the main program.

    :param int   k: A limiter that specifies how many log files to process
    :param str dir: The directory where the log files live
    """
    dir_entries = [os.path.join(dir, i) for i in os.listdir(dir)]
    logs_dirs = [entry for entry in dir_entries if os.path.isdir(entry)]

    log_files = []

    for dir in logs_dirs:
        log_files.extend([os.path.join(dir, entry) for entry in os.listdir(dir)])

    records = []

    errors = {}

    cpus = os.cpu_count()
    # cores = cpus - (cpus // 4)
    cores = cpus

    chunks = [[] for _ in range(cores)]

    if k != -1:
        # log_files = log_files[:k]
        log_files = random.sample(log_files, k=k)

    for i in range(len(log_files)):
        chunks[i % cores].append(log_files[i])

    workers = []

    for chunk in chunks:
        thread = Thread(target=process_chunk, args=(chunk, records, errors))
        thread.start()

        workers.append(thread)

    for worker in workers:
        worker.join()

    return records, errors


if __name__ == "__main__":
    records, errors = main()

    diagnosis = [errors[name]["diagnosis"] for name in errors]
    from collections import Counter

    diagnosis = dict(Counter(diagnosis))

    # migrate_to_db(jsons, errors)
    print("Done")

    print(errors)
    print(len(errors))

    with open("errors.txt", "w") as file:
        try:
            content = json.dumps(errors, indent=4)
        except Exception as e:
            content = str(errors)
            print(e)

        file.write(content)
