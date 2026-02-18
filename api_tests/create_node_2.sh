#!/usr/bin/env bash

token=$(tail -n 1 cookies.txt | awk -F '\t' '{print $NF}')

# Delete it first if it exists
curl \
    -X DELETE \
    -H "Authorization: $token" \
    http://localhost:5000/api/nodes/id_node_2

curl \
    -X POST \
    -H "Authorization: $token" \
    -H "Content-Type: application/json" \
    -d '{
            "_id": "id_node_2",
            "profile": {
                "position": "48.805662, -3.565364",
                "token": "L3yDozfwVicwMuXBRyYXuhah5Qvw1sM8qT2NdRX3oz8"
            }
        }' \
    http://localhost:5000/api/nodes/

# The trailing / is important
