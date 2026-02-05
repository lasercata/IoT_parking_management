from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.virtualization.digital_replica.dr_factory import DRFactory

nodes_api = Blueprint('nodes_api', __name__,url_prefix = '/api/nodes')

def register_node_blueprint(app):
    app.register_blueprint(nodes_api)

@nodes_api.route('/', methods=['GET'])
def list_nodes():
    '''Gets all nodes with optional filtering on `status`.'''

    try:
        filters = {}
        if request.args.get('status'):
            filters["data.status"] = request.args.get('status')

        nodes = current_app.config["DB_SERVICE"].query_drs('node', filters)

        # Remove token from results
        nodes_cleaned = []
        for n in nodes:
            nodes_cleaned.append({
                '_id': n['_id'],
                'status': n['data']['status'],
                'position': n['profile']['position'],
                # 'metadata': n['metadata'], #TODO: add this data for admin only
                # 'used_by': n['used_by'],
            })

        return jsonify({"nodes": nodes_cleaned}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@nodes_api.route('/', methods=['POST'])
def create_node():
    '''
    Creates a new node.

    Data to post:
    {
        "_id": str,
        "profile": {
            "position": str,
            "token": str
        }
    }
    '''

    try:
        data = request.get_json()
        dr_factory = DRFactory("src/virtualization/templates/node.yaml")
        node = dr_factory.create_dr('node', data)
        node_id = current_app.config["DB_SERVICE"].save_dr("node", node)

        return jsonify({"status": "success", "message": "Node created successfully", "node_id": node_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@nodes_api.route('/<node_id>', methods=['GET'])
def get_node(node_id):
    '''Gets node details'''

    try:
        node = current_app.config["DB_SERVICE"].get_dr("node", node_id)
        if not node:
            return jsonify({"error": "node not found"}), 404

        # Remove token from results
        node_cleaned = {
            '_id': node['_id'],
            'status': node['data']['status'],
            'position': node['profile']['position'],
            # 'metadata': node['metadata'], #TODO: add this data for admin only
            # 'used_by': node['used_by'],
        }

        return jsonify(node_cleaned), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@nodes_api.route('/<node_id>', methods=['POST'])
def authentication_request(node_id):
    '''
    Processes the authentication requests sent by the node <node_id>.

    This request should be composed of the following data:
    {
        user_data: {
            'UID': str,
            'AUTH_BYTES': str,
            'NEW_AUTH_BYTES': str,
        },
        token: str
    }

    It first authenticates the node by checking if `token` matches.
    '''

    raise NotImplementedError('TODO') #TODO

    try:
        data = request.get_json()

        return jsonify({"status": "success", "message": "node updated successfully"}), 200

    except Exception as e:
        return jsonify({"error":str(e)}),500

@nodes_api.route("/<node_id>", methods=['PATCH'])
def update_node(node_id):
    '''
    Updates node details, especially status.

    Example data:
    {
        "data": {
            "status": str
        }
    }
    '''

    try:
        data = request.get_json()
        update_data = {}

        # Handle profile updates
        if "profile" in data:
            #TODO: allow admin to do it, refuse others.
            return jsonify({'error': 'Not allowed to edit profile'}), 403

        #Handle data updates
        if "data" in data:
            if "used_by" in data['data']:
                #TODO: allow admin to do it, refuse others.
                return jsonify({'error': 'Not allowed to edit used_by'}), 403

            update_data["data"] = data["data"]

        #Always update the 'updated at' timestamp
        update_data["metadata"] = {"updated_at": datetime.utcnow()}

        current_app.config["DB_SERVICE"].update_dr("node", node_id,update_data)
        return jsonify({"status": "success", "message": "node updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@nodes_api.route("/<node_id>", methods=['DELETE'])
def delete_node(node_id):
    '''Deletes a node.'''

    try:
        node = current_app.config["DB_SERVICE"].get_dr("node", node_id)

        if not node:
            return jsonify({"error": "node not found"}), 404

        current_app.config["DB_SERVICE"].delete_dr("node", node_id)

        return jsonify({"status": "success", "message": "node deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
