#!/bin/sh

/usr/bin/ssh -vvN -gD 4450 \
    -o PreferredAuthentications=publickey \
    -o StrictHostKeyChecking=accept-new \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=2 \
    -i /home/ssh/key \
    $*
