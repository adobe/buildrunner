import pytest

from buildrunner.config import models
from buildrunner.config import models_step


@pytest.mark.parametrize(
    "global_config, step_config, merged_config",
    [
        # Override nothing (no step config)
        (
            {},
            None,
            {
                "enabled": False,
                "scanner": "trivy",
                "version": "latest",
                "cache-dir": None,
                "config": {
                    "timeout": "20m",
                    "exit-code": 0,
                },
                "max-score-threshold": None,
            },
        ),
        # Override enabled only
        (
            {},
            {"enabled": True},
            {
                "enabled": True,
                "scanner": "trivy",
                "version": "latest",
                "cache-dir": None,
                "config": {
                    "timeout": "20m",
                    "exit-code": 0,
                },
                "max-score-threshold": None,
            },
        ),
        # Override everything
        (
            {
                "enabled": True,
                "scanner": "global-scanner",
                "version": "global-version",
                "cache-dir": "global-cache",
                "max-score-threshold": 1.1,
            },
            {
                "enabled": False,
                "scanner": "step-scanner",
                "version": "step-version",
                "config": {
                    "exit-code": 1,
                    "step-config": True,
                },
                "max-score-threshold": 2.1,
            },
            {
                "enabled": False,
                "scanner": "step-scanner",
                "version": "step-version",
                "cache-dir": "global-cache",
                "config": {
                    "timeout": "20m",
                    "exit-code": 1,
                    "step-config": True,
                },
                "max-score-threshold": 2.1,
            },
        ),
    ],
)
def test_security_scan_config_merge(global_config, step_config, merged_config):
    global_security_scan_config = models.GlobalSecurityScanConfig(**global_config)
    step_security_scan_config = (
        models_step.StepPushSecurityScanConfig(**step_config) if step_config else None
    )

    merged_security_scan_config = global_security_scan_config.merge_scan_config(
        step_security_scan_config
    )
    assert merged_security_scan_config == models.GlobalSecurityScanConfig(
        **merged_config
    )

    # Make sure the original object was unchanged
    assert (
        models.GlobalSecurityScanConfig(**global_config) == global_security_scan_config
    )
