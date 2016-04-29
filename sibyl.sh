#!/usr/bin/env bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH="$dir/.."
cd "$dir"
(setsid python run.py -d &)

sleep 2
if [ ! -f /var/run/sibyl/sibyl.pid ]; then
  exit 1
fi
