"""
Usage:

    python -m modast.apply_dir <directory>

This recursively walks into the given `<directory>` and apply the transformation
for all `.py` files.
"""

import sys
import os

from modast import run


def main():
    [dirpath] = sys.argv[1:]
    print(f"Apply guards in directory: {dirpath}")
    for dirpath, _, filenames in os.walk(dirpath):
        for filepath in filenames:
            if filepath.endswith(".py"):
                fullpath = os.path.join(dirpath, filepath)
                print(f"Working on {fullpath!r}")
                run(fullpath)


if __name__ == "__main__":
    main()
