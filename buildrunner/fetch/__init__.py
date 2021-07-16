"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import urllib.parse

from . import github
from . import http
from . import file


def fetch_file(url, config):
    """
    Fetch a file from a provider.
    """

    # pylint: disable=fixme
    # FIXME: the handled checking should be in each handler module (possibly handle_file(parsed_url,
    # config) => bool)

    parsed_url = urllib.parse.urlparse(url)

    if parsed_url.scheme == 'github':
        file_contents = github.fetch_file(parsed_url, config)

    elif parsed_url.scheme == 'file' or (parsed_url.scheme == '' and parsed_url.netloc == ''):
        purl = list(parsed_url)
        purl[0] = 'file'
        parsed_url = urllib.parse.ParseResult(*purl)
        file_contents = file.fetch_file(parsed_url, config)

    elif parsed_url.scheme in ('http', 'https'):
        file_contents = http.fetch_file(parsed_url, config)

    else:
        raise NotImplementedError(f'Unknown fetch backend: {parsed_url.scheme}')

    return file_contents

# Local Variables:
# fill-column: 100
# End:
