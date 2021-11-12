"""
A watchdog on directory to automatically apply the transformations.
"""
import os
import sys
import time
import traceback

# import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


from modast.modast import run


class WatchDog(FileSystemEventHandler):
    def on_modified(self, event: FileSystemEvent):
        self.run(event)

    # def on_created(self, event: FileSystemEvent):
    #     self.run(event)

    def run(self, event: FileSystemEvent):
        path = event.src_path

        if event.is_directory:
            return

        if path.endswith(".py"):
            print(event)
            try:
                run(path)
            except Exception as e:
                print("Ignored exception")
                traceback.print_exc()


if __name__ == "__main__":
    # logging.basicConfig(
    #     level=logging.INFO,
    #     format="%(asctime)s - %(message)s",
    #     datefmt="%Y-%m-%d %H:%M:%S",
    # )
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    event_handler = WatchDog()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
