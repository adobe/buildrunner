"""
Copyright (C) 2023 Adobe
"""

from __future__ import print_function

import importlib.machinery
import os
import subprocess
import sys
import types

from setuptools import setup, find_packages


BASE_VERSION = "3.9"

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDRUNNER_DIR = os.path.join(SOURCE_DIR, "buildrunner")
VERSION_FILE = os.path.join(BUILDRUNNER_DIR, "version.py")

THIS_DIR = os.path.dirname(__file__)


def read_requirements(filename):
    """
    :param filename:
    """
    requires = []
    dep_links = []
    try:
        with open(os.path.join(THIS_DIR, filename)) as robj:
            lnr = 0
            for line in robj.readlines():
                lnr += 1
                _line = line.strip()
                if not _line:
                    continue
                if _line.startswith("#"):
                    continue

                if _line.startswith("--extra-index-url"):
                    args = _line.split(None, 1)
                    if len(args) != 2:
                        print(
                            'ERROR: option "--extra-index-url" must have a URL argument: {}:{}'.format(
                                filename, lnr
                            ),
                            file=sys.stderr,
                        )
                        continue
                    dep_links.append(args[1])

                elif _line[0].isalpha():
                    # See note in Dockerfile for why this replacement is done
                    requires.append(_line.replace("jaraco-classes", "jaraco.classes"))

                else:
                    print(
                        'ERROR: {}:{}:"{}" does not appear to be a requirement'.format(
                            filename, lnr, _line
                        ),
                        file=sys.stderr,
                    )

    except IOError as err:
        sys.stderr.write('Failure reading "{0}": {1}\n'.format(filename, err))
        sys.exit(err.errno)

    return requires, dep_links


REQUIRES, DEP_LINKS = read_requirements("requirements.txt")
requirements, dependency_links = read_requirements("test_requirements.txt")
TEST_REQUIRES = requirements
DEP_LINKS.extend(dependency_links)


def get_version():
    """
    Call out to the git command line to get the current commit "number".
    """
    if os.path.exists(VERSION_FILE):
        # Read version from file
        loader = importlib.machinery.SourceFileLoader(
            "buildrunner_version", VERSION_FILE
        )
        version_mod = types.ModuleType(loader.name)
        loader.exec_module(version_mod)
        existing_version = version_mod.__version__  # pylint: disable=no-member
        return existing_version

    # Generate the version from the base version and the git commit number, then store it in the file
    try:
        cmd = subprocess.Popen(
            args=[
                "git",
                "rev-list",
                "--count",
                "HEAD",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf8",
        )
        stdout = cmd.communicate()[0]
        output = stdout.strip()
        if cmd.returncode == 0:
            new_version = "{0}.{1}".format(BASE_VERSION, output)

            # write the version file
            if os.path.exists(BUILDRUNNER_DIR):
                with open(VERSION_FILE, "w", encoding="utf8") as _fobj:
                    _fobj.write("__version__ = '%s'\n" % new_version)
            return new_version
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Could not generate version from git commits: {exc}")
    # If all else fails, use development version
    return f"{BASE_VERSION}.DEVELOPMENT"


with open(os.path.join(os.path.dirname(__file__), "README.rst")) as fobj:
    long_description = fobj.read().strip()

setup(
    name="buildrunner",
    version=get_version(),
    author="Adobe",
    author_email="noreply@adobe.com",
    license="MIT",
    url="https://github.com/adobe/buildrunner",
    description="Docker-based build tool",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    scripts=[
        "bin/buildrunner",
        "bin/buildrunner-cleanup",
    ],
    package_data={
        "buildrunner": ["SourceDockerfile"],
        "buildrunner.sshagent": [
            "SSHAgentProxyImage/Dockerfile",
            "SSHAgentProxyImage/run.sh",
            "SSHAgentProxyImage/login.sh",
        ],
    },
    install_requires=REQUIRES,
    tests_require=TEST_REQUIRES,
    dependency_links=DEP_LINKS,
    test_suite="tests",
)

# Local Variables:
# fill-column: 100
# End:
