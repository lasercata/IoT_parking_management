#!/usr/bin/env bash

curl \
    -X POST \
    --cookie-jar cookies.txt \
    -d "username=usr1&password=azer" \
    http://localhost:3000/login
