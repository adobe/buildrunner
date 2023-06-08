"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
import base64
import requests

from ..errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProtocolError,
)


def v3_fetch_file(parsed_url, config):
    """
    Fetch files using Github v3 protocol.
    """

    endpoint = config.get('endpoint')
    version = config.get('version')

    username = config.get('username', os.getenv('USER', os.getenv('LOGNAME')))
    if not username:
        raise RuntimeError(f'Failed to look up username to access github {endpoint}')

    auth = (username, config.get('app_token', ''))
    url = '/'.join((
        endpoint,
        version,
        'users',
        username,
    ))
    resp = requests.get(url, auth=auth, timeout=180)
    if resp.status_code != 200:
        raise BuildRunnerProtocolError(f'Failed authenticating {username} on {endpoint}')

    if not parsed_url.path.startswith('/'):
        raise ValueError('URL must begin with "/"')

    fpath = parsed_url.path.split('/')
    ubuild = [endpoint, version, 'repos', fpath[1], fpath[2], 'contents']
    ubuild.extend(fpath[3:])
    url = '/'.join(ubuild)
    resp = requests.get(url, auth=auth, timeout=180)
    if resp.status_code != 200:
        raise BuildRunnerProtocolError(f'Failed fetching URL: {url}')
    json_c = resp.json()

    encoding = json_c.get('encoding')
    enc_contents = json_c.get('content')
    if encoding == 'base64':
        dec_contents = base64.b64decode(enc_contents)
    else:
        raise NotImplementedError(
            f'No implementation to decode {encoding}-encoded contents'
        )

    if resp.encoding == 'utf-8':
        contents = dec_contents.decode('utf-8')
    else:
        raise NotImplementedError(
            f'No implementation to decode {resp.encoding}-encoded contents'
        )

    return contents


def fetch_file(parsed_url, config):
    """
    Fetch a file from Github.
    """

    if parsed_url.scheme != 'github':
        raise ValueError(f'URL scheme must be "github" but is "{parsed_url.github}"')

    ghcfg = config.get('github')
    if not ghcfg:
        raise BuildRunnerConfigurationError('Missing configuration for github in buildrunner.yaml')

    nlcfg = ghcfg.get(parsed_url.netloc)
    if not nlcfg:
        gh_cfgs = ', '.join(ghcfg.keys())
        raise BuildRunnerConfigurationError(
            f'Missing github configuration for {parsed_url.netloc} in buildrunner.yaml'
            f' - known github configurations: {gh_cfgs}'
        )

    ver = nlcfg.get('version')
    # NOTE: potentially the v3_fetch_file() works for other github API versions.
    if ver == 'v3':
        contents = v3_fetch_file(parsed_url, nlcfg)
    else:
        raise NotImplementedError(f'No version support for github API version {ver}')

    return contents
