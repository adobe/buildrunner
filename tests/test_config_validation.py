
import buildrunner.config_model as config_model
from pydantic import ValidationError
import pytest


def test_valid_version_config():
    #  Invalid version
    config = {
        'version': 'string'
    }
    with pytest.raises(ValidationError):
        config_model.Config(**config)

    #  Valid version
    config = {
        'version': 2.0,
        'steps': {
        }
    }
    try:
        config_model.Config(**config)
    except ValidationError as err:
        pytest.fail(f'Config should be valid {err}')

    # Optional version
    config = {
        'steps': {
        }
    }
    try:
        config_model.Config(**config)
    except ValidationError as err:
        pytest.fail(f'Config should be valid {err}')

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
    with pytest.raises(ValueError):
        config_model.Config(**config)


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
    with pytest.raises(ValueError):
        config_model.Config(**config)

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
    model = config_model.Config(**config)
    assert model.steps['build-container-multi-platform']
    assert model.steps['build-container-multi-platform'].build
    assert model.steps['build-container-multi-platform'].build.platforms == ['linux/amd64', 'linux/arm64']
    assert model.steps['build-container-multi-platform'].build.platform is None


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
    with pytest.raises(ValueError):
        config_model.Config(**config)

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
    with pytest.raises(ValueError):
        config_model.Config(**config)

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
    with pytest.raises(ValueError):
        config_model.Config(**config)

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
    model = config_model.Config(**config)
    assert model.steps['build-container-multi-platform1']
    assert model.steps['build-container-multi-platform1'].build
    assert model.steps['build-container-multi-platform1'].build.platforms == ['linux/amd64', 'linux/arm64']
    assert model.steps['build-container-multi-platform1'].build.platform is None
    assert model.steps['build-container-multi-platform1'].push == 'mytest-reg/buildrunner-test-multi-platform:latest'

    assert model.steps['build-container-multi-platform2']
    assert model.steps['build-container-multi-platform2'].build
    assert model.steps['build-container-multi-platform2'].build.platforms == ['linux/amd64', 'linux/arm64']
    assert model.steps['build-container-multi-platform2'].build.platform is None
    assert model.steps['build-container-multi-platform2'].push == 'mytest-reg/buildrunner-test-multi-platform:not-latest'

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
    with pytest.raises(ValueError):
        config_model.Config(**config)

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

    try:
        model = config_model.Config(**config)
        assert model.steps
        assert model.version

    except ValidationError as err:
        pytest.fail(f'Config should be valid {err}')
