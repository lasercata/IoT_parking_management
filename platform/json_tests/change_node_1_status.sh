#!/usr/bin/env bash

curl \
    -X PATCH \
    -H "Content-Type: application/json" \
    -d '{
            "data": {
                "status": "occupied"
            }
        }' \
    http://localhost:5000/api/nodes/c7e99b8b-fb48-4e62-b418-c2002c25f968

