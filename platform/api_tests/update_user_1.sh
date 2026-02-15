#!/usr/bin/env bash

token=$(tail -n 1 ../../frontend/api_tests/cookies.txt | awk -F '\t' '{print $NF}')

curl \
    -X PATCH \
    -H "Authorization: $token" \
    -H "Content-Type: application/json" \
    -d '{
        "pwd_hash": ""
    }' \
    http://localhost:5000/api/users/DEADBEEF

