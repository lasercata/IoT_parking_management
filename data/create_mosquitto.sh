#!/usr/bin/env bash

mkdir -p mosquitto/config
mkdir -p mosquitto/certs
mkdir -p mosquitto/log

touch mosquitto/log/mosquitto.log
# touch mosquitto/config/passwd
#
# chmod 0600 mosquitto/config/passwd

chown -R 3333:3333 mosquitto/

