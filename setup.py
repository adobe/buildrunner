"""
Copyright (C) 2014 Adobe
"""
import os

from setuptools import setup, find_packages
import vcsinfo

_VERSION = '0.5'

_SOURCE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

try:
    # calculate the version
    VCS = vcsinfo.detect_vcs(_SOURCE_DIR)
    _VERSION += '.%s' % VCS.number
    if VCS.modified > 0:
        _VERSION += '.%s' % VCS.modified

    # write the version file
    _BUILDRUNNER_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'buildrunner',
    )
    if os.path.exists(_BUILDRUNNER_DIR):
        with open(os.path.join(_BUILDRUNNER_DIR, 'version.py'), 'w') as _ver:
            _ver.write("__version__ = '%s'\n" % _VERSION)
except vcsinfo.VCSUnsupported:
    _VERSION += '.DEVELOPMENT'


#pylint: disable=C0301
setup(
    name='buildrunner',
    version=_VERSION,
    author='***REMOVED***',
    author_email="***REMOVED***",
    license="Adobe",
    url="https://***REMOVED***/***REMOVED***/buildrunner",
    description="",
    long_description="",

    packages=find_packages(),
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
    install_requires=[
        'PyYAML==3.11',
        'requests==2.9.1',
        'paramiko==1.16.0',
        'pycrypto==2.6.1',
        'docker-py==1.3.1',
        'vcsinfo>=0.1.23',
        'fabric==1.10.1',
        'Jinja2==2.7.3',
    ],
)
