'''
Fetch GitHub files.

Copyright (C) 2019 Adobe
'''

from __future__ import absolute_import

import os
import sys
import base64
import requests

from ..errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProtocolError,
)

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse


def v3_fetch_file(parsed_url, config):
    '''
    Fetch files using Github v3 protocol.
    '''

    endpoint = config.get('endpoint')
    version = config.get('version')

    username = config.get('username', os.getenv('USER', os.getenv('LOGNAME')))
    if not username:
        raise RuntimeError('Failed to look up username to access github {}'.format(endpoint))

    auth = (username, config.get('app_token', ''))
    url = '/'.join((
        endpoint,
        version,
        'users',
        username,
    ))
    resp = requests.get(url, auth=auth)
    if resp.status_code != 200:
        raise BuildRunnerProtocolError('Failed authentication to {}'.format(endpoint))

    if not parsed_url.path.startswith('/'):
        raise ValueError('URL must begin with "/"')

    fpath = parsed_url.path.split('/')
    ubuild = [endpoint, version, 'repos', fpath[1], fpath[2], 'contents']
    ubuild.extend(fpath[3:])
    url = '/'.join(ubuild)
    resp = requests.get(url, auth=auth)
    if resp.status_code != 200:
        raise BuildRunnerProtocolError('Failed fetching URL: {}'.format(url))
    json_c = resp.json()

    encoding = json_c.get('encoding')
    enc_contents = json_c.get('content')
    if encoding == 'base64':
        dec_contents = base64.b64decode(enc_contents)
    else:
        raise NotImplementedError(
            'No implementation to decode {}-encoded contents'.format(encoding)
        )

    if resp.encoding == 'utf-8':
        contents = dec_contents.decode('utf-8')
    else:
        raise NotImplementedError(
            'No implementation to decode {}-encoded contents'.format(resp.encoding)
        )

    return contents


def fetch_file(parsed_url, config):
    '''
    Fetch a file from Github.
    '''

    if parsed_url.scheme != 'github':
        raise ValueError('URL scheme must be "github" but is "{}"'.format(parsed_url.github))

    ghcfg = config.get('github')
    if not ghcfg:
        raise BuildRunnerConfigurationError('Missing configuration for github in buildrunner.yaml')

    nlcfg = ghcfg.get(parsed_url.netloc)
    if not nlcfg:
        raise BuildRunnerConfigurationError(
            (
                'Missing github configuration for {} in buildrunner.yaml'
                ' - known github configurations: {}'
            ).format(parsed_url.netloc, ghcfg.keys())
        )

    ver = nlcfg.get('version')
    # FIXME: potentially the v3_fetch_file() works for other github API versions.
    if ver == 'v3':
        contents = v3_fetch_file(parsed_url, nlcfg)
    else:
        raise NotImplementedError('No version support for github {}'.format(ver))

    return contents


# Local Variables:
# fill-column: 100
# End:
