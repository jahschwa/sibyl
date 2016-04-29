#!/usr/bin/env bash

(setsid python run.py & echo $! > /var/run/sibyl.pid)
