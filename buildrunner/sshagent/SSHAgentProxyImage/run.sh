#!/bin/sh

# take a ssh public key as a single argument and add to authorized_keys
echo $1 > /root/.ssh/authorized_keys

# generate new sshd keys
/usr/sbin/sshd-keygen

# run the sshd server
/usr/sbin/sshd -D

