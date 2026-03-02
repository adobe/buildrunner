import pytest


@pytest.mark.parametrize(
    "config_yaml, error_matches",
    [
        # Valid memory limit as string
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          mem-limit: "512m"
          cmd: echo "test"
    """,
            [],
        ),
        # Valid memory limit as integer (bytes)
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          mem-limit: 536870912
          cmd: echo "test"
    """,
            [],
        ),
        # Valid CPU shares
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          cpu-shares: 512
          cmd: echo "test"
    """,
            [],
        ),
        # Valid CPU period and quota
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          cpu-period: 100000
          cpu-quota: 50000
          cmd: echo "test"
    """,
            [],
        ),
        # Valid all resource limits together
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          mem-limit: "1g"
          cpu-shares: 1024
          cpu-period: 100000
          cpu-quota: 100000
          cmd: echo "test"
    """,
            [],
        ),
        # Valid service with resource limits
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          services:
            db:
              image: postgres:13
              mem-limit: "256m"
              cpu-shares: 512
          cmd: echo "test"
    """,
            [],
        ),
        # Invalid CPU shares (should be integer)
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          cpu-shares: "invalid"
          cmd: echo "test"
    """,
            ["Input should be a valid integer"],
        ),
        # Invalid CPU period (should be integer)
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          cpu-period: "invalid"
          cmd: echo "test"
    """,
            ["Input should be a valid integer"],
        ),
        # Invalid CPU quota (should be integer)
        (
            """
    steps:
      test-step:
        run:
          image: ubuntu:20.04
          cpu-quota: "invalid"
          cmd: echo "test"
    """,
            ["Input should be a valid integer"],
        ),
    ],
)
def test_resource_limits_validation(config_yaml, error_matches):
    """Test that resource limit configuration is validated correctly."""
    from buildrunner.config.models import generate_and_validate_config

    config, errors = generate_and_validate_config(**{
        "steps": __import__("yaml").safe_load(config_yaml)["steps"]
    })

    if error_matches:
        assert errors is not None
        for error_match in error_matches:
            assert any(error_match in error for error in errors)
    else:
        assert errors is None
        assert config is not None
