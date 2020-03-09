"""
Copyright (C) 2014-2017 Adobe
"""

from __future__ import print_function

import imp
import os
import subprocess
import sys
import unittest

from setuptools import setup, find_packages


_VERSION = '0.6'

_SOURCE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)
_BUILDRUNNER_DIR = os.path.join(_SOURCE_DIR, 'buildrunner')
_VERSION_FILE = os.path.join(_BUILDRUNNER_DIR, 'version.py')

THIS_DIR = os.path.dirname(__file__)
REQUIRES = []
DEP_LINKS = []
for require in ('requirements.txt', 'test_requirements.txt'):
    with open(os.path.join(THIS_DIR, require)) as robj:
        lnr = 0
        for line in robj.readlines():
            lnr += 1
            _line = line.strip()
            if not _line:
                continue

            if _line.startswith('--extra-index-url'):
                args = _line.split(None, 1)
                if len(args) != 2:
                    print(
                        'ERROR: option "--extra-index-url" must have a URL argument: {}:{}'.format(
                            require,
                            lnr
                        ),
                        file=sys.stderr,
                    )
                    continue
                DEP_LINKS.append(args[1])

            elif _line[0].isalpha():
                REQUIRES.append(_line)

            else:
                print(
                    'ERROR: {}:{}:"{}" does not appear to be a requirement'.format(
                        require,
                        lnr,
                        _line
                    ),
                    file=sys.stderr,
                )
                pass


def get_version():
    """
    Call out to the git command line to get the current commit "number".
    """
    _ver = _VERSION

    try:
        cmd = subprocess.Popen(
            args=[
                'git',
                'rev-list',
                '--count',
                'HEAD',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout = cmd.communicate()[0]
        outdata = stdout.strip().decode('utf-8')
        if cmd.returncode == 0:
            _version = '{0}.{1}'.format(_ver, outdata)

            # write the version file
            if os.path.exists(_BUILDRUNNER_DIR):
                with open(_VERSION_FILE, 'w') as _ver:
                    _ver.write("__version__ = '%s'\n" % _version)
    except: #pylint: disable=bare-except
        pass

    if os.path.exists(_VERSION_FILE):
        version_mod = imp.load_source('buildrunnerversion', _VERSION_FILE)
        _version = version_mod.__version__
    else:
        _version += '.DEVELOPMENT'

    return _version


setup(
    name='buildrunner',
    version=get_version(),
    author='***REMOVED***',
    author_email="***REMOVED***",
    license="Adobe",
    url="https://***REMOVED***/***REMOVED***/buildrunner",
    description="Docker-based build enviroment",
    long_description="",

    packages=find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']),
    scripts=[
        'bin/buildrunner',
    ],
    package_data={
        'buildrunner' : ['SourceDockerfile'],
        'buildrunner.sshagent' : [
            'SSHAgentProxyImage/Dockerfile',
            'SSHAgentProxyImage/run.sh',
            'SSHAgentProxyImage/login.sh',
        ],
    },
    install_requires=REQUIRES,
    dependency_links=DEP_LINKS,
    test_suite='tests',
)


# Local Variables:
# fill-column: 100
# End:
