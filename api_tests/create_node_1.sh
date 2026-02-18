#!/usr/bin/env bash

token=$(tail -n 1 cookies.txt | awk -F '\t' '{print $NF}')

# Delete it first if it exists
curl \
    -X DELETE \
    -H "Authorization: $token" \
    http://localhost:5000/api/nodes/id_node_1

curl \
    -X POST \
    -H "Authorization: $token" \
    -H "Content-Type: application/json" \
    -d '{
            "_id": "id_node_1",
            "profile": {
                "position": "39.193154, 9.159417",
                "token": "FMe8EDbSBhIgkjzvXHJqDUDc2chQL8zKQgyMA0cTJTc"
            }
        }' \
    http://localhost:5000/api/nodes/

# The trailing / is important
