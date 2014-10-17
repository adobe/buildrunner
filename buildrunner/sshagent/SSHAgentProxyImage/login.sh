#!/bin/sh

if [ -z "$SSH_AUTH_SOCK" ]; then
    echo "Can only connect when SSH agent forwarding is enabled."
else
    #while :
    #do
    #    rm -f /ssh-agent/agent
    #    socat UNIX-LISTEN:/ssh-agent/agent "UNIX:$SSH_AUTH_SOCK"
    #done
    rm -f /ssh-agent/agent
    socat UNIX-LISTEN:/ssh-agent/agent,fork "UNIX:$SSH_AUTH_SOCK"
fi

