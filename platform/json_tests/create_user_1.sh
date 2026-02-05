#!/usr/bin/env bash

curl \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "_id": "DEADBEEF",
        "profile": {
            "username": "usr1",
            "email": "usr1@example.com",
            "is_admin": false
        }
    }' \
    http://localhost:5000/api/users/

