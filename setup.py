"""
Copyright (C) 2014 Adobe
"""
from setuptools import setup, find_packages
import vcsinfo

#pylint: disable=C0301
setup(
    name='buildrunner',
    version='0.1',
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
    },
    install_requires=[
        'PyYAML==3.10',
        'docker-py==0.4.0',
        'vcsinfo>=0.1.13',
        'fabric==1.10.0',
    ],

    # override the default egg_info class to enable setting the tag_build
    cmdclass={
        'egg_info': vcsinfo.VCSInfoEggInfo,
    },
)
