#!/usr/bin/env bash

# Extract token from cookies file
token=$(tail -n 1 cookies.txt | awk -F '\t' '{print $NF}')

curl \
    -H "Authorization: $token" \
    http://localhost:5000/api/nodes/
