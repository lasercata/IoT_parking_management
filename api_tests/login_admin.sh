#!/usr/bin/env bash

curl \
    -X POST \
    --cookie-jar cookies.txt \
    -d "username=admin&password=azer" \
    http://localhost:3000/login
