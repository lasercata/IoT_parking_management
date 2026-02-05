#!/usr/bin/env bash

curl \
    -X POST \
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
