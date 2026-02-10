#!/usr/bin/env bash

token=$(tail -n 1 ../../frontend/test_with_curl/cookies.txt | awk -F '\t' '{print $NF}')

# Delete it first if it exists
curl \
    -X DELETE \
    -H "Authorization: Bearer $token" \
    http://localhost:5000/api/users/DEADBEEF

# Create it
curl \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -d '{
        "_id": "DEADBEEF",
        "profile": {
            "username": "usr1",
            "email": "usr1@example.com",
            "is_admin": false,
            "badge_expiration": "2027-01-01"
        }
    }' \
    http://localhost:5000/api/users/

