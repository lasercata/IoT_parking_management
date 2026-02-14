#!/usr/bin/env bash

token=$(tail -n 1 ../../frontend/test_with_curl/cookies.txt | awk -F '\t' '{print $NF}')

curl \
    -X GET \
    -H "Authorization: $token" \
    http://localhost:5000/api/users/pwd_reset

