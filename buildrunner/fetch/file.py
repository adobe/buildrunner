"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import codecs


def fetch_file(parsed_url, config):  # pylint: disable=unused-argument
    """
    Pull files from the local file system.
    """
    with codecs.open(parsed_url.path, 'r', encoding='utf-8') as _file:
        contents = ''.join(_file.readlines())

    return contents
