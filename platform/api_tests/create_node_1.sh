#!/usr/bin/env bash

token=$(tail -n 1 ../../frontend/api_tests/cookies.txt | awk -F '\t' '{print $NF}')

# Delete it first if it exists
curl \
    -X DELETE \
    -H "Authorization: $token" \
    http://localhost:5000/api/nodes/c7e99b8b-fb48-4e62-b418-c2002c25f968

curl \
    -X POST \
    -H "Authorization: $token" \
    -H "Content-Type: application/json" \
    -d '{
            "_id": "c7e99b8b-fb48-4e62-b418-c2002c25f968",
            "profile": {
                "position": "39.193154, 9.159417",
                "token": "8sLpdyl81TyqqoU8HNPdNQ=="
            }
        }' \
    http://localhost:5000/api/nodes/

# The trailing / is important
