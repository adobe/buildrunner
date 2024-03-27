"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import urllib.parse
from typing import Optional

from ..models import GlobalConfig
from . import github
from . import http
from . import file


def fetch_file(url: str, config: Optional[GlobalConfig]) -> str:
    """
    Fetch a file from a provider.
    """

    # pylint: disable=fixme
    # FIXME: the handled checking should be in each handler module (possibly handle_file(parsed_url,
    # config) => bool)

    parsed_url = urllib.parse.urlparse(url)
    scheme = parsed_url.scheme
    if isinstance(scheme, bytes):
        scheme = scheme.decode("utf8")

    if scheme == "github":
        file_contents = github.fetch_file(parsed_url, config)

    elif scheme == "file" or (
        scheme == "" and (parsed_url.netloc == "" or parsed_url.netloc == b"")
    ):
        purl = list(parsed_url)
        purl[0] = "file"
        parsed_url = urllib.parse.ParseResult(*purl)
        file_contents = file.fetch_file(parsed_url, config)

    elif scheme in ("http", "https"):
        file_contents = http.fetch_file(parsed_url, config)

    else:
        raise NotImplementedError(f"Unknown fetch backend: {scheme}")

    return file_contents


# Local Variables:
# fill-column: 100
# End:
