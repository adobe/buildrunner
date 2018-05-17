"""
Copyright (C) 2014-2017 Adobe
"""
import imp
import os
import subprocess

from setuptools import setup, find_packages


_VERSION = '0.6'

_SOURCE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)
_BUILDRUNNER_DIR = os.path.join(_SOURCE_DIR, 'buildrunner')
_VERSION_FILE = os.path.join(_BUILDRUNNER_DIR, 'version.py')


def get_version():
    """
    Call out to the git command line to get the current commit "number".
    """
    _version = _VERSION

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
        if cmd.returncode == 0:
            _version += '.%s' % stdout.strip()

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
        'vcsinfo==0.1.30',
        'requests==2.9.1',
        'paramiko==1.16.0',
        'pycrypto==2.6.1',
        'docker==2.3.0',
        'fabric==1.10.1',
        'Jinja2==2.7.3',
    ],
    dependency_links=[
        'https://***REMOVED***/artifactory/***REMOVED***/vcsinfo/0.1.30/vcsinfo-0.1.30.tar.gz#egg=vcsinfo-0.1.30', #pylint: disable=line-too-long
    ],
)

