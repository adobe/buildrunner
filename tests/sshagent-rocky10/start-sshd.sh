#!/bin/bash
set -euo pipefail

ssh-keygen -A
git init -q /tmp/origin
printf 'Buildrunner SSH-agent smoke test\n' > /tmp/origin/README
git -C /tmp/origin add README
git -C /tmp/origin -c user.name=Probe -c user.email=probe@example.invalid commit -qm fixture
git clone -q --bare /tmp/origin /tmp/probe.git

cat > /tmp/sshd_config <<'CONFIG'
Port 2222
HostKey /etc/ssh/ssh_host_rsa_key
AuthorizedKeysFile /source/authorized_keys
StrictModes no
UsePAM no
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
AuthenticationMethods publickey
LogLevel DEBUG3
PidFile /run/sshd-probe.pid
CONFIG

printf 'PubkeyAcceptedKeyTypes %s\n' \
    "${PROBE_ACCEPTED_ALGORITHMS:-rsa-sha2-256,rsa-sha2-512}" >> /tmp/sshd_config
/usr/sbin/sshd -T -f /tmp/sshd_config > /probe-results/server-config.log
exec /usr/sbin/sshd -D -E /probe-results/sshd.log -f /tmp/sshd_config
