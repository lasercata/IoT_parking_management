#!/usr/bin/env bash

token=$(tail -n 1 cookies.txt | awk -F '\t' '{print $NF}')

curl \
    -X GET \
    -H "Authorization: $token" \
    http://localhost:5000/api/users/

