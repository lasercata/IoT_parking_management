#!/usr/bin/env bash

token=$(tail -n 1 ../../frontend/api_tests/cookies.txt | awk -F '\t' '{print $NF}')

# Delete it first if it exists
curl \
    -X DELETE \
    -H "Authorization: $token" \
    http://localhost:5000/api/users/2c18f1f8-5b8f-43a8-8f03-68ef1486453e

# Create it
curl \
    -X POST \
    -H "Authorization: $token" \
    -H "Content-Type: application/json" \
    -d '{
        "_id": "2c18f1f8-5b8f-43a8-8f03-68ef1486453e",
        "profile": {
            "username": "admin",
            "email": "admin@lasercata.com",
            "is_admin": true
        }
    }' \
    http://localhost:5000/api/users/

