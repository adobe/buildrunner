'''
File fetching engine.

Copyright (C) 2019 Adobe
'''

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

from . import github
from . import http
from . import file


def fetch_file(url, config):
    '''
    Fetch a file from a provider.
    '''

    # FIXME: the handled checking should be in each handler module (possibly handle_file(parsed_url,
    # config) => bool)

    parsed_url = urlparse.urlparse(url)

    if parsed_url.scheme == 'github':
        file_contents = github.fetch_file(parsed_url, config)

    elif parsed_url.scheme == '' and parsed_url.netloc == '':
        purl = list(parsed_url)
        purl[0] = 'file'
        parsed_url = urlparse.ParseResult(*purl)
        file_contents = file.fetch_file(parsed_url, config)

    elif parsed_url.scheme in ('http', 'https'):
        file_contents = http.fetch_file(parsed_url, config)

    else:
        raise NotImplementedError('Unknown provider: {}'.format(parsed_url.scheme))

    return file_contents


# Local Variables:
# fill-column: 100
# End:
