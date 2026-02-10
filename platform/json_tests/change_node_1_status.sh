#!/usr/bin/env bash

token=$(tail -n 1 ../../frontend/test_with_curl/cookies.txt | awk -F '\t' '{print $NF}')

curl \
    -X PATCH \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -d '{
            "data": {
                "status": "occupied"
            }
        }' \
    http://localhost:5000/api/nodes/c7e99b8b-fb48-4e62-b418-c2002c25f968

