#!/usr/bin/env bash

cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"/..
(setsid python sibyl/run.py & echo $! > /var/run/sibyl/sibyl.pid)
