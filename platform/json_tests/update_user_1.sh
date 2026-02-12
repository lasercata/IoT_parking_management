#!/usr/bin/env bash

token=$(tail -n 1 ../../frontend/test_with_curl/cookies.txt | awk -F '\t' '{print $NF}')

curl \
    -X PATCH \
    -H "Authorization: $token" \
    -H "Content-Type: application/json" \
    -d '{
        "pwd_hash": ""
    }' \
    http://localhost:5000/api/users/DEADBEEF

