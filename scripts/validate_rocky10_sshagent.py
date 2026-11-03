"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from paramiko import RSAKey
import yaml

import buildrunner.config
from buildrunner import cli


def main():
    """Prepare a tiny source repository and invoke the real Buildrunner CLI."""
    parser = argparse.ArgumentParser(
        description="Run the Rocky Linux 10 SSH-agent smoke test with a disposable RSA key."
    )
    parser.add_argument("--temp-dir", default=os.environ.get("BUILDRUNNER_TEMPDIR"))
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Also verify ssh-rsa/SHA-1 using an isolated Rocky 8 client/server.",
    )
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="buildrunner-rocky10-", dir=args.temp_dir))
    project = root / "project"
    project.mkdir()
    fixture = Path(__file__).resolve().parent.parent / "tests" / "sshagent-rocky10"
    for name in ["buildrunner.yaml", "start-sshd.sh", "validate.sh"]:
        shutil.copyfile(str(fixture / name), str(project / name))
    if args.include_legacy:
        job = yaml.safe_load((project / "buildrunner.yaml").read_text())
        legacy = yaml.safe_load((fixture / "buildrunner-legacy.yaml").read_text())
        job["steps"].update(legacy["steps"])
        (project / "buildrunner.yaml").write_text(yaml.safe_dump(job, sort_keys=False))

    # Keep the private key outside the source archive and all container mounts.
    private_key = root / "id_rsa"
    key = RSAKey.generate(2048)
    key.write_private_key_file(str(private_key))
    assert private_key.read_text().startswith("-----BEGIN RSA PRIVATE KEY-----")
    (project / "authorized_keys").write_text("ssh-rsa " + key.get_base64() + "\n")
    config = root / "global.yaml"
    config.write_text(
        yaml.safe_dump({
            "docker-registry": "docker.io",
            "ssh-keys": [{"file": str(private_key), "aliases": ["probe-rsa"]}],
        })
    )

    try:
        subprocess.check_call(["git", "init", "-q", str(project)])
        subprocess.check_call(["git", "-C", str(project), "add", "."])
        subprocess.check_call([
            "git",
            "-C",
            str(project),
            "-c",
            "user.name=Probe",
            "-c",
            "user.email=probe@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-qm",
            "Disposable SSH-agent fixture",
        ])

        # Do not load the user's global configuration or unrelated real keys.
        buildrunner.config.DEFAULT_GLOBAL_CONFIG_FILES = []
        print("Smoke-test workspace: " + str(root), flush=True)
        print("Test key: 2048-bit RSA in traditional PKCS#1 PEM format.", flush=True)
        sys.argv = [
            "buildrunner",
            "--directory",
            str(project),
            "--global-config",
            str(config),
            "--file",
            str(project / "buildrunner.yaml"),
            "--build-number",
            "sshagent-probe",
            "--no-color",
            "--local-images",
        ]
        return cli.main()
    finally:
        private_key.unlink()
        print("Disposable private key removed.", flush=True)
        print("Results: " + str(project / "buildrunner.results"), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
