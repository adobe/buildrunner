#!/bin/bash
set -euo pipefail

mkdir -p /source/validation /root/.ssh
cat /etc/rocky-release
ssh -V
printf 'Crypto policy: '
cat /etc/crypto-policies/config

test "${SSH_AUTH_SOCK}" = /ssh-agent/agent
test -S "${SSH_AUTH_SOCK}"
test ! -e /source/id_rsa
test ! -e /root/.ssh/id_rsa
ssh-add -l | tee /source/validation/agent.log
test "$(ssh-add -l | awk '{print $2}')" = \
     "$(ssh-keygen -lf /source/authorized_keys | awk '{print $2}')"

# The server is isolated on this job's Docker network and has a fresh host key.
for attempt in $(seq 1 30); do
    if ssh-keyscan -T 2 -t rsa -p 2222 ssh-target > /root/.ssh/known_hosts 2>/dev/null; then
        break
    fi
    sleep 1
done
test -s /root/.ssh/known_hosts

for requested in ${PROBE_SIGNATURE_ALGORITHMS:-default rsa-sha2-256 rsa-sha2-512}; do
    export GIT_SSH_COMMAND="ssh -vvv -F /dev/null -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o IdentityAgent=${SSH_AUTH_SOCK} -o IdentitiesOnly=yes -i /source/authorized_keys -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/.ssh/known_hosts"
    if [ "${requested}" != default ]; then
        GIT_SSH_COMMAND="${GIT_SSH_COMMAND} -o PubkeyAcceptedKeyTypes=${requested}"
    fi
    git clone "ssh://root@ssh-target:2222/tmp/probe.git" \
        "/source/validation/${requested}" \
        > "/source/validation/${requested}.stdout.log" \
        2> "/source/validation/${requested}.client.log"
    algorithm=$(sed -n 's/.*sign_and_send_pubkey: signing using \([^[:space:]]*\).*/\1/p' \
        "/source/validation/${requested}.client.log")
    case "${algorithm}" in
        rsa-sha2-256|rsa-sha2-512) ;;
        ssh-rsa) test "${requested}" = ssh-rsa ;;
        *) printf 'Unexpected signature algorithm: %s\n' "${algorithm}"; exit 1 ;;
    esac
    if [ "${requested}" != default ]; then
        test "${algorithm}" = "${requested}"
    fi
    printf 'Clone mode: %s; signature: %s\n' "${requested}" "${algorithm}"
    grep -F 'Buildrunner SSH-agent smoke test' "/source/validation/${requested}/README"
    grep -F "sign_and_send_pubkey: signing using ${algorithm}" \
        "/source/validation/${requested}.client.log"
    if [ "${algorithm}" = ssh-rsa ]; then
        # OpenSSH 8 logs verification without the algorithm name. Assert that
        # the server accepts only ssh-rsa, then check its successful verification.
        grep -E '^pubkeyaccepted(keytypes|algorithms) ssh-rsa$' /probe-results/server-config.log
        grep -E 'mm_answer_keyverify: publickey .*signature (using ssh-rsa )?verified' \
            /probe-results/sshd.log
    else
        grep -F "publickey RSA signature using ${algorithm} verified" /probe-results/sshd.log
    fi
    if grep -E 'incorrect signature type|no mutual signature supported|Permission denied' \
        "/source/validation/${requested}.client.log"; then
        exit 1
    fi
done

cp /probe-results/sshd.log /source/validation/server.log
cp /probe-results/server-config.log /source/validation/server-config.log
printf 'PASS: all Git clones used the injected agent and server-verified requested signatures.\n' \
    | tee /source/validation/result.txt
