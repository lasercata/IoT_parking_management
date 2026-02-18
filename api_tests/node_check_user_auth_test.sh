#!/usr/bin/env bash

curl \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "token": "FMe8EDbSBhIgkjzvXHJqDUDc2chQL8zKQgyMA0cTJTc",
        "user_data": {
            "UID": "DEADBEEF",
            "AUTH_BYTES": "0000000000000000",
            "NEW_AUTH_BYTES": "0000000000000000"
        }
    }' \
    https://api.iot.lasercata.com/api/nodes/node_0
    # http://localhost:5000/api/nodes/c7e99b8b-fb48-4e62-b418-c2002c25f968
