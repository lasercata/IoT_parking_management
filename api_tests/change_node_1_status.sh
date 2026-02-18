#!/usr/bin/env bash

token=$(tail -n 1 cookies.txt | awk -F '\t' '{print $NF}')

# # By node (status: free)
# curl \
#     -X PATCH \
#     -H "Content-Type: application/json" \
#     -d '{
#             "data_to_update": {
#                 "status": "free"
#             },
#             "source": "node",
#             "token": "8sLpdyl81TyqqoU8HNPdNQ=="
#         }' \
#     http://localhost:5000/api/nodes/c7e99b8b-fb48-4e62-b418-c2002c25f968

# By user (status: reserved, i.e reservation of the node)
curl \
    -X PATCH \
    -H "Authorization: $token" \
    -H "Content-Type: application/json" \
    -w "%{http_code}\n" \
    -d '{
            "data_to_update": {
                "status": "free"
            },
            "source": "ui"
        }' \
    http://localhost:5000/api/nodes/id_node_3

# # By admin ()
# curl \
#     -X PATCH \
#     -H "Authorization: $token" \
#     -H "Content-Type: application/json" \
#     -d '{
#             "data_to_update": {
#                 "status": "violation",
#                 "used_by": ""
#             },
#             "source": "ui"
#         }' \
#     http://localhost:5000/api/nodes/c7e99b8b-fb48-4e62-b418-c2002c25f968
