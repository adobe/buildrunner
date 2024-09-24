"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import sys
from xml.etree import ElementTree


def run(files):
    first = None
    for filename in files:
        data = ElementTree.parse(filename).getroot()
        if first is None:
            first = data
        else:
            first.extend(data)
    if first is not None:
        print(ElementTree.tostring(first, encoding="unicode"))


if __name__ == "__main__":
    run(sys.argv[1:])
