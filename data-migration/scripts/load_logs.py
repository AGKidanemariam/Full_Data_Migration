import os
from pathlib import Path
from threading import Thread

try:
    LOG_FILE_DIR_LOC = Path("../../Log Files/Logs/").resolve()
    assert LOG_FILE_DIR_LOC.exists(), "Could not find log file directory"
except AssertionError:
    LOG_FILE_DIR_LOC = Path("../Log Files/Logs/").resolve()
    assert LOG_FILE_DIR_LOC.exists(), "Could not find log file directory"


class File:
    def __init__(self, loc):
        self.name = loc
        self.content = None

    def read(self):
        with open(self.name, "r") as file:
            self.content = file.read()

    @staticmethod
    def read_instantly(file: str) -> File:
        f = File(file)
        f.read()
        return f


    def __repr__(self):
        return "<File Object>"


def read_batch(batch: list[str], result: list[str]) -> list[File]:
    for i in range(len(batch)):
        result.append(File.read_instantly(batch[i]))


def load_logs(*, dir=LOG_FILE_DIR_LOC, k=-1):
    cpus = os.cpu_count()

    partitions = [[] for _ in range(cpus)]
    entries = os.listdir(dir)

    print("Loading up target files in batches...")
    count = 0
    for entry in entries:
        for file in os.listdir(LOG_FILE_DIR_LOC / entry):
            fullpath = LOG_FILE_DIR_LOC / entry / file
            partitions[count % cpus].append(fullpath)
            count += 1


    print("Reading batches...")

    result = []
    workers = []
    for batch in partitions:
        worker = Thread(target=read_batch, args=(batch, result))
        worker.start()
        workers.append(worker)

    count = 1
    for worker in workers:
        worker.join()
        print(f"{count} / {cpus} workers are done.")
        count += 1

    return result


if __name__ == "__main__":
    # run `py -i load_logs.py`
    logs = load_logs()
