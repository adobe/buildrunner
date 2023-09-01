
from buildrunner.validation.config_model import validate_config, Errors


def test_valid_version_config():
    #  Invalid version
    config = {
        'version': 'string'
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

    #  Valid version
    config = {
        'version': 2.0,
        'steps': {
        }
    }
    errors = validate_config(**config)
    assert errors is None

    # Optional version
    config = {
        'steps': {
        }
    }
    errors = validate_config(**config)
    assert errors is None


def test_platform_and_platforms_invalid():
    # Invalid to have platform and platforms
    config = {
        'steps': {
            'build-container-multi-platform': {
                'build': {
                    'path': '.',
                    'dockerfile': 'Dockerfile',
                    'pull': False,
                    'platform': 'linux/amd64',
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test-multi-platform',
                    'tags': [ 'latest' ],
                },
            },
        }
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_platforms_invalid():
    # Invalid to have platforms as a string, it should be a list
    config = {
        'steps': {
            'build-container-multi-platform': {
                'build': {
                    'path': '.',
                    'dockerfile': 'Dockerfile',
                    'pull': False,
                    'platforms': 'linux/amd64',
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test-multi-platform',
                    'tags': [ 'latest' ],
                },
            },
        }
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 2


def test_build_is_path():
    config = {
        'steps': {
            'build-is-path': {
                'build': '.',
            },
        }
    }
    errors = validate_config(**config)
    assert errors is None


def test_valid_platforms():
    config = {
        'steps': {
            'build-container-multi-platform': {
                'build': {
                    'path': '.',
                    'dockerfile': 'Dockerfile',
                    'pull': False,
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test-multi-platform',
                    'tags': [ 'latest' ],
                },
            },
        }
    }
    errors = validate_config(**config)
    assert errors is None


def test_duplicate_mp_tags_dictionary_invalid():
    # Invalid to have duplicate multi-platform tag
    # Testing with both dictionary format
    config = {
        'steps': {
            'build-container-multi-platform1': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test-multi-platform',
                    'tags': [ 'latest' ],
                },
            },
            'build-container-multi-platform2': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test-multi-platform',
                    'tags': [ 'latest' ],
                },
            },
        }
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_duplicate_mp_tags_strings_invalid():
    # Invalid to have duplicate multi-platform tag
    # Testing with both string format, one inferred 'latest' the other explicit 'latest'
    config = {
        'steps': {
            'build-container-multi-platform1': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                # No tag is given so 'latest' is assumed
                'push': 'mytest-reg/buildrunner-test-multi-platform',
            },
            'build-container-multi-platform2': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': 'mytest-reg/buildrunner-test-multi-platform:latest',
            },
        }
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

    # Indentical tags in same string format
    config = {
        'steps': {
            'build-container-multi-platform1': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': 'mytest-reg/buildrunner-test-multi-platform:latest',
            },
            'build-container-multi-platform2': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': 'mytest-reg/buildrunner-test-multi-platform:latest',
            },
        }
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_duplicate_mp_tags_strings_valid():
    #  Same string format but different MP tags
    config = {
        'steps': {
            'build-container-multi-platform1': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': 'mytest-reg/buildrunner-test-multi-platform:latest',
            },
            'build-container-multi-platform2': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': 'mytest-reg/buildrunner-test-multi-platform:not-latest',
            },
        }
    }
    errors = validate_config(**config)
    assert errors is None


def test_duplicate_mp_tags_platform_platforms_invalid():
    # Invalid to have duplicate multi-platform tag and single platform tag
    config = {
        'steps': {
            'build-container-multi-platform1': {
                'build': {
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': 'mytest-reg/buildrunner-test-multi-platform:latest',
            },
            'build-container-single-platform': {
                'build': {
                    'platform': 'linux/arm64'
                },
                'push': 'mytest-reg/buildrunner-test-multi-platform:latest',
            },
        }
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_valid_config():
    # Sample valid config, but not exhaustive
    config = {
        'version': 2.0,
        'steps': {
            'build-container-single-platform1': {
                'build': {
                    'path': '.',
                    'dockerfile': 'Dockerfile',
                    'pull': False,
                    'platform': 'linux/amd64',
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test',
                    'tags': [ 'latest' ],
                },
            },
            'build-container-multi-platform2': {
                'build': {
                    'path': '.',
                    'dockerfile': 'Dockerfile',
                    'pull': False,
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test-multi-platform',
                    'tags': [ 'latest' ],
                },
            },
            'build-container-multi-platform-push3': {
                'build': {
                    'path': '.',
                    'dockerfile': 'Dockerfile',
                    'pull': False,
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': [
                    'myimages/image1',
                    {
                        'repository': 'myimages/image2',
                        'tags': [ 'latest' ],
                    }
                ],
            },
        }
    }

    errors = validate_config(**config)
    assert errors is None


def test_multiple_errors():
    # Multiple errors
    # Invalid to have version as a string
    # Invalid to have platforms and platform
    config = {
        'version': 'string',
        'steps': {
            'build-container-multi-platform': {
                'build': {
                    'path': '.',
                    'dockerfile': 'Dockerfile',
                    'pull': False,
                    'platform': 'linux/amd64',
                    'platforms': [
                        'linux/amd64',
                        'linux/arm64',
                    ],
                },
                'push': {
                    'repository': 'mytest-reg/buildrunner-test-multi-platform',
                    'tags': [ 'latest' ],
                },
            },
        }
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 2
