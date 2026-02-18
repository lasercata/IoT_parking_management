#!/usr/bin/env bash

# This is to test if messages are published.
#
# Usage:
#   ./mosquitto_subscriber "username" "password"

mosquitto_sub \
    -h broker.iot.lasercata.com \
    -p 8883 \
    -u "$1" \
    -P "$2" \
    -d \
    -t "nodes/+"
    # --cafile ../../data/mosquitto/certs/ca.crt \
    # --insecure
