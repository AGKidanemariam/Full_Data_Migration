import time
from dataclasses import dataclass
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..macs_parser.core import _split_raw_rows
from ..macs_parser.utils import find_str_indexes, extract_timestamp
from ..macs_parser import mappings
from ..macs_parser import Record, TemporaryRecordRegistry
from ..macs_parser import DISCRIMINATOR_MAPPING
from ..macs_parser import preprocess_content, get_key_indexes, get_column_names, has_multiplexed_schema


@dataclass
class LogFileNodeContext:
    origin: str
    rel_path: str
    delimiter: str
    last_byte_read: int
    is_multiplexed: bool
    column_names: list[list[str]]

    def __init__(
        self,
        *,
        origin,
        rel_path,
        column_names,
        last_byte_read,
        delimiter="\t",
        controller_signed_on=None
    ):
        self.origin = origin
        self.rel_path = rel_path
        self.column_names = column_names
        self.is_multiplexed = has_multiplexed_schema(column_names)
        self.delimiter = delimiter,
        self.last_byte_read = last_byte_read
        self.controller_signed_on = controller_signed_on


class LogFileNode:
    def __init__(self, context: LogFileNodeContext) -> None:
        self.context = context
        self.registry = TemporaryRecordRegistry()

        if self.context.is_multiplexed:

            for column_name_schema in self.context.column_names:
                discriminator = column_name_schema[0]
                column_names = column_name_schema[1:]
                self.registry.create_record(discriminator, column_names)

        else:
            # not a multiplexed log file, just a file with one column name line defined
            self.registry.create_record(None, self.context.column_names[0])

    def add_row(self, row: list[str]):
        if self.context.is_multiplexed:
            discriminator = DISCRIMINATOR_MAPPING.get(row[0], row[0])
            values = row[1:]
            self.registry.add_row(discriminator, values)
        else:
            discriminator = None
            self.registry.add_row(discriminator, row)

    def add_all_rows(self, rows: list[list[str]]):
        for row in rows:
            self.add_row(row)



class EventHandler(FileSystemEventHandler):
    def __init__(self, delimiter="\t") -> None:
        super().__init__()
        self.delimiter = delimiter

        # self.orm = ORM(database_url)
        # self.orm.initialize()

        self.nodes: dict[str, LogFileNode] = {}

    def _create_node(self, src_path: str, byte_content: bytes) -> LogFileNode:
        content = byte_content.decode()
        line_content = preprocess_content(content, self.delimiter)

        file_name_idx = find_str_indexes(line_content, ["file name: "])[0]
        origin_file_name = line_content[file_name_idx].split(": ")[1].strip()

        (
            preceding_col_idx,
            preceding_row_idx,
            end_header_idx
        ) = get_key_indexes(line_content)

        column_names: list[list[str]] = get_column_names(line_content, preceding_col_idx, end_header_idx, "\t")

        node = LogFileNode(
            LogFileNodeContext(
                origin=origin_file_name,
                rel_path=src_path,
                column_names=column_names,
                last_byte_read=len(byte_content)
            )
        )

        return node

    def _process_incoming_rows(self, src_path: str, raw_rows: list[str]):
        """
        Process incoming lines from a log file and update the corresponding LogFileNode.
        """
        node: LogFileNode = self.nodes[src_path]

        if raw_rows[0].startswith("Controller "):
            controller_signed_on_timestamp = extract_timestamp(raw_rows[0])
            node.context.controller_signed_on = controller_signed_on_timestamp
            raw_rows = raw_rows[1:]
            print("Controller signed on: ", str(controller_signed_on_timestamp))

        if len(raw_rows) == 0:
            print("No new change happened")
            return

        rows = _split_raw_rows(raw_rows, self.delimiter)

        node.add_all_rows(rows)

        print(node.registry.records)

    # Triggered when a file or directory is created
    def on_created(self, event):
        if not event.src_path.endswith(".log"):
            return

        print(f"Created: {event.src_path}")

        with open(event.src_path, "rb") as file:
            byte_content = file.read()

        try:
            node = self._create_node(event.src_path, byte_content)
        except Exception as e:
            print(f"Error creating node for `{event.src_path}`: ", e)
            return

        print("\n============")
        print("Node Details")
        print("============\n")

        print(node.context.rel_path)
        print(node.context.origin)
        print(f"{node.context.is_multiplexed=}")
        # print([rec.fields for rec in node.registry.get_all_records()])
        print(node.context.column_names)
        print(node.registry.get_all_records())

        # self.nodes[node.context.rel_path] = node
        self.nodes[event.src_path] = node

        # if rows still exist when a file is created, uncomment the following lines
        # raw_rows = preprocess_content(byte_content.decode())
        # self._process_incoming_rows(event.src_path, raw_rows)

    def _update_node(self, node: LogFileNode, byte_content: bytes):
        content = byte_content.decode()
        print("\n=================")
        print("New content added")
        print("=================\n")

        raw_rows = preprocess_content(content, self.delimiter)

        self._process_incoming_rows(node.context.rel_path, raw_rows)

        node.context.last_byte_read += len(byte_content)

    # Triggered when a file or directory is modified
    def on_modified(self, event):
        print(f"Modified: {event.src_path}")

        node: LogFileNode = self.nodes[event.src_path]

        with open(event.src_path, "rb") as file:
            file.seek(node.context.last_byte_read)

            new_byte_content = file.read()

            if len(new_byte_content) == 0:
                print("No new change happened")
                return

        try:
            self._update_node(node, new_byte_content)
        except Exception as e:
            print(f"Error updating node `{event.src_path}`: ", e)
            return

    # Triggered when a file or directory is deleted
    def on_deleted(self, event):
        if event.src_path in self.nodes:
            self.nodes.pop(event.src_path)
        print(f"Deleted: {event.src_path}")


def start_directory_monitor(dir_to_watch: str, recursive: bool):
    observer = Observer()
    event_handler = EventHandler()

    observer.schedule(event_handler, path=dir_to_watch, recursive=recursive)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    print("Started monitor testing...")
    start_directory_monitor("test", recursive=False)
