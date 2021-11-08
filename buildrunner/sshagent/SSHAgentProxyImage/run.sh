#!/bin/sh

# take a ssh public key as a single argument and add to authorized_keys
echo $1 > /root/.ssh/authorized_keys

# generate sshd keys
/usr/libexec/openssh/sshd-keygen rsa
/usr/libexec/openssh/sshd-keygen dsa
/usr/libexec/openssh/sshd-keygen ecdsa
/usr/libexec/openssh/sshd-keygen ed25519

# run the sshd server
/usr/sbin/sshd -D

