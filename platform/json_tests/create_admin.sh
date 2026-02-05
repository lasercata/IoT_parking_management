#!/usr/bin/env bash

curl \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "_id": "2c18f1f8-5b8f-43a8-8f03-68ef1486453e",
        "profile": {
            "username": "admin",
            "email": "admin@example.com",
            "is_admin": true
        }
    }' \
    http://localhost:5000/api/users/

