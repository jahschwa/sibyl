#!/usr/bin/env bash

cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
(setsid python run.py -d &)

sleep 2
if [ ! -f /var/run/sibyl/sibyl.pid ]; then
  exit 1
fi
