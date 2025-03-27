"""
Copyright 2025 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import os
import subprocess


def main():
    base_dir = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
    base_version_file = os.path.join(base_dir, "BASE_VERSION")

    with open(base_version_file, "r") as file:
        base_version = file.read().strip()

    major, minor = map(int, base_version.split(".")[:2])

    try:
        commit_count = (
            subprocess.check_output(["git", "rev-list", "--count", "HEAD"])
            .strip()
            .decode("utf-8")
        )
    except Exception:
        commit_count = "0"

    version_file = os.path.join(base_dir, "buildrunner", "version.py")

    version = f"{major}.{minor}.{commit_count}"
    with open(version_file, "w") as version_file:
        version_file.write(f'__version__ = "{version}"\n')


if __name__ == "__main__":
    main()
