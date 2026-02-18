#!/usr/bin/env bash

# Extract token from cookies file
token=$(tail -n 1 cookies.txt | awk -F '\t' '{print $NF}')

curl \
    -H "Authorization: $token" \
    https://api.iot.lasercata.com/api/users/
    # http://localhost:5000/api/users/
