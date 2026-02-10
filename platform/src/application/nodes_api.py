from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.virtualization.digital_replica.dr_factory import DRFactory
from src.application.authentication import token_required, is_admin, authenticate_node
from src.application.user_management import UserCheck

nodes_api = Blueprint('nodes_api', __name__,url_prefix = '/api/nodes')

def register_node_blueprint(app):
    app.register_blueprint(nodes_api)

@nodes_api.route('/', methods=['GET'])
@token_required()
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
            })

            # For admins, add more data
            if is_admin():
                nodes_cleaned[-1]['metadata'] = n['metadata']
                nodes_cleaned[-1]['used_by'] = n['used_by']

        return jsonify({"nodes": nodes_cleaned}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@nodes_api.route('/', methods=['POST'])
@token_required(only_admins=True)
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
@token_required()
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
        }

        # For admins, add more data
        if is_admin():
            node_cleaned['metadata'] = node['metadata']
            node_cleaned['used_by'] = node['used_by']

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

    Out:
        Always returns a json in the form:
            {status: str, message: str}

        `status` indicates the type of return, and `message` gives more details

        Status values:
            - error: request error (payload form) or node authentication error
            - invalid: unkown user, badge expired, already parked, parking reserved by an other
            - violation: badge cloning detected
            - success: all checks passed, user is legally parked
    '''

    try:
        #---Init
        data = request.get_json()

        #---Node authentication
        # Check that node exists
        node = current_app.config['DB_SERVICE'].get_dr('node', node_id)
        if not node:
            return jsonify({'status': 'error', 'message': 'node not found'}), 404

        # Authenticate the node
        if 'token' not in data:
            return jsonify({'status': 'error', 'message': 'Missing authentication token (node secret token)'}), 401

        if not authenticate_node(current_app.config['DB_SERVICE'], node_id, data['token']):
            return jsonify({'status': 'error', 'message': 'Wrong authentication token (node secret token)'}), 403

        #---Check payload integrity
        if 'user_data' not in data:
            return jsonify({'status': 'error', 'message': 'Malformed request: missing "user_data" field'}), 400

        if any(field not in data['user_data'] for field in ('UID', 'AUTH_BYTES', 'NEW_AUTH_BYTES')):
            return jsonify({'status': 'error', 'message': 'Malformed request: the field "user_data" should contain { UID: str, AUTH_BYTES: str, NEW_AUTH_BYTES: str }'}), 400

        #---Check user
        # Init
        user_data = data['user_data']
        uid = user_data['UID']
        user_checker = UserCheck(current_app.config["DB_SERVICE"], uid)

        # Check that user exists
        if not user_checker.is_uid_valid():
            return jsonify({'status': 'invalid', 'message': 'invalid UID'}), 404

        # Check user authentication
        if not user_checker.is_authenticated(user_data['AUTH_BYTES'], user_data['NEW_AUTH_BYTES']):
            user_checker.send_cloning_event()
            return jsonify({'status': 'violation', 'message': 'Wrong authentication token'}), 403

        # Check user authorization (badge expiration)
        if not user_checker.is_authorized():
            return jsonify({'status': 'invalid', 'mesasge': 'User not authorized (badge expired)'}), 403

        # Check multi parking
        if user_checker.is_already_parked():
            return jsonify({'status': 'invalid', 'message': 'User already parked'}), 403

        #---Check parking spot reservation
        if node['data']['status'] == 'reserved':
            if node['used_by'] != uid:
                return jsonify({'status': 'invalid', 'message': 'Parking reserved by an other user'}), 403

        elif node['data']['status'] != 'free':
            return jsonify({'status': 'error', 'message': 'Parking not in free state'}), 403

        #---All the check passed!
        # Set user.is_parked = True
        current_app.config['DB_SERVICE'].update_dr('user', uid, {'is_parked': True})

        # Set `node.status = occupied` and `node.used_by = UID`
        current_app.config['DB_SERVICE'].update_dr('node', node_id, {'data': {'status': 'occupied'}, 'used_by': uid})

        return jsonify({'status': 'success', 'message': 'User is legally parked'}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@nodes_api.route("/<node_id>", methods=['PATCH'])
def update_node(node_id): #TODO
    '''
    Updates node details, especially status.

    Example data:
    {
        "data": {
            "status": str
        },
        "from": str,       # ("node" | "UI")
        "token": str       # Only needed when "from": "node"
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
@token_required(only_admins=True)
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
