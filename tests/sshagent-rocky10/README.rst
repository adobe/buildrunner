Rocky Linux 10 SSH-agent smoke test
========================================

This opt-in Docker test runs a real Buildrunner job, including its SSH-agent
proxy container and agent forwarding. A Rocky Linux 10 build container clones a
disposable Git repository from a local SSH service using default negotiation,
then explicitly requiring ``rsa-sha2-256`` and ``rsa-sha2-512``. The server
rejects SHA-1.

The job checks the injected key's fingerprint, the client's selected signing
algorithm, the server's successful cryptographic verification of that algorithm,
and the cloned file contents. Client/server logs are collected as artifacts.

No corporate services or credentials are used. The helper creates a temporary
RSA key outside the source directory, injects only its public key into the test
containers, and deletes the private key afterward. It bypasses the user's
global Buildrunner configuration. Containers are cleaned up by Buildrunner;
temporary source files, logs, and test images are retained for inspection.

From the repository root, using an environment with the project's requirements
installed and access to a running Docker engine::

    docker build -t buildrunner-rocky10-sshagent-test:latest tests/sshagent-rocky10
    docker pull busybox:latest
    PYTHONPATH=. python scripts/validate_rocky10_sshagent.py

Set ``DOCKER_HOST`` if needed; on Docker Desktop for macOS the default socket
is typically ``unix:///var/run/docker.sock``. ``--temp-dir`` optionally selects
where the helper creates its isolated workspace. The output prints the results
directory, including the Buildrunner log and archived validation artifacts.

Legacy RSA/SHA-1 compatibility
----------------------------------------

RSA key age and signature algorithm are separate: the same RSA private key can
produce SHA-1 or SHA-2 signatures. The helper uses traditional PKCS#1 PEM
(``BEGIN RSA PRIVATE KEY``) format, as commonly used by older RSA keys.

To additionally check an older client requesting ``ssh-rsa``/SHA-1, build the
isolated Rocky Linux 8.5 test image and enable the legacy job::

    docker build --build-arg ROCKY_IMAGE=rockylinux:8.5 \
        -t buildrunner-legacy-sshagent-test:latest tests/sshagent-rocky10
    PYTHONPATH=. python scripts/validate_rocky10_sshagent.py --include-legacy

Both jobs use the same generated RSA key. The Rocky 10 server still rejects
SHA-1; a separate Rocky 8 server accepts only ``ssh-rsa`` for authentication.
This verifies the unchanged zero-flag legacy signing path without weakening
the Rocky 10 test. Neither test bypasses minimum-key-size policies: very small
RSA keys may still be rejected by modern SSH/crypto policy.
