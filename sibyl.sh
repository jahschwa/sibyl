#!/usr/bin/env bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
(setsid python "$dir/run.py" & echo $! > /var/run/sibyl/sibyl.pid)
