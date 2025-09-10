"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from typing import Optional

from ..models import GlobalConfig


def fetch_file(parsed_url, config: Optional[GlobalConfig]):
    """
    Fetch files using HTTP.
    """

    raise NotImplementedError("Not Implemented: fetch.http.file_fetch")
