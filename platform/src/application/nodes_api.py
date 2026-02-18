from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.application.node_management import NodeManagement
from src.application.authentication import decode_token, token_required, is_admin, authenticate_node
from src.application.user_management import UserCheck
from src.virtualization.digital_replica.dr_factory import DRFactory

nodes_api = Blueprint('nodes_api', __name__,url_prefix = '/api/nodes')

def register_node_blueprint(app):
    app.register_blueprint(nodes_api)

@nodes_api.route('/', methods=['GET'])
@token_required()
def list_nodes():
    '''
    Gets all nodes with optional filtering on `status`.
    It is also possible to list the nodes reserved by self (from token) with `used_by_me`

    E.g
        GET /api/nodes/
        GET /api/nodes/?status=free
        GET /api/nodes/?used_by_me
        GET /api/nodes/?status=free&used_by_me
    '''

    try:
        filters = {}
        if request.args.get('status'):
            filters['data.status'] = request.args.get('status')

        if 'used_by_me' in request.args:
            filters['used_by'] = decode_token()['uid']

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
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        Always returns a tuple[json, int] in the form:
            {status: str, message: str}, http_code

        `status` indicates the type of return, and `message` gives more details

        Status values:
            - error: request error (payload form) or node authentication error
            - invalid: unknown user, badge expired, already parked, parking reserved by an other
            - violation: badge cloning detected
            - success: all checks passed, user is legally parked
    '''

    try:
        #---Init
        data = request.get_json()

        #---Node authentication
        # Check that node exists
        node_management = NodeManagement(node_id, current_app.config['DB_SERVICE'], current_app.config['MQTT_HANDLER'])
        if not node_management.is_id_valid():
            return jsonify({'status': 'error', 'message': 'node not found'}), 404

        # Authenticate the node
        if 'token' not in data:
            return jsonify({'status': 'error', 'message': 'Missing authentication token (node secret token)'}), 401

        if not authenticate_node(current_app.config['DB_SERVICE'], node_id, data['token']):
            return jsonify({'status': 'error', 'message': 'Authentication failed! Wrong node secret token'}), 403

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
            # Send cloning notification
            user_checker.send_cloning_event(node_id)

            # Set node status to violation
            node_management.update_content({'data': {'status': 'violation'}})

            # Return
            return jsonify({'status': 'violation', 'message': 'Wrong authentication token'}), 403

        # Check user authorization (badge expiration)
        if not user_checker.is_authorized():
            return jsonify({'status': 'invalid', 'mesasge': 'User not authorized (badge expired)'}), 403

        # Check multi parking
        if user_checker.is_already_parked():
            return jsonify({'status': 'invalid', 'message': 'User already parked'}), 403

        #---Check parking spot reservation
        if node_management.get_status() == 'reserved':
            if node_management.get()['used_by'] == uid:
                # Remove the corresponding reservation
                user_checker.decrease_nb_reservations()
            else:
                return jsonify({'status': 'invalid', 'message': 'Parking reserved by an other user'}), 403

        elif node_management.get_status() != 'free':
            return jsonify({'status': 'error', 'message': 'Parking not in free state'}), 403

        #---All the check passed!
        # Set user.is_parked = True
        user_checker.update_content({'is_parked': True})

        # Set `node.status = occupied` and `node.used_by = UID`
        node_management.update_content({'data': {'status': 'occupied'}, 'used_by': uid})

        return jsonify({'status': 'success', 'message': 'User is legally parked'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@nodes_api.route("/<node_id>", methods=['PATCH'])
def update_node(node_id):
    '''
    Updates node details, especially status.

    Who can hit this endpoint?
        - node: change the status (from its FSM)
        - user: make a reservation
        - admin: change anything

    Payload format (simple):
    {
        "data_to_update": {
            "status": str
        },
        "source": str,     # ("node" | "ui")
        "token": str       # Only needed when "source": "node"
    }

    Payload format (complete, note that only admin can edit some fields):
    {
        "data_to_update": {
            "status": str,       # permission: node, user, admin
            "used_by": str,      # permission: only admin
            "profile": {         # permission: only admin
                "position": str,
                "token": str
            }
        },
        "source": str,     # ("node" | "ui")
        "token": str       # Only needed when "source": "node"
    }

    Out:
        Always returns a tuple[json, int] in the form:
            {status: str, message: str}, http_code

        `status` indicates the type of return, and `message` gives more details

        Status values:
            - error: request error (e.g payload format)
            - auth_err: authentication error
            - perm_err: permission error (e.g user tries to edit node profile (token))
            - reservation_error: reservation cannot be made (e.g someone took the place before)
            - success: value updated
    '''

    try:
        #---Check that node exists
        node_management = NodeManagement(node_id, current_app.config['DB_SERVICE'], current_app.config['MQTT_HANDLER'])
        if not node_management.is_id_valid():
            return jsonify({'status': 'error', 'message': 'node not found'}), 404

        #---Init
        data = request.get_json()

        #---Validate the data
        # Source
        if 'source' not in data:
            return jsonify({'status': 'error', 'message': 'Field "source" missing in payload'}), 400

        if data['source'] not in ('node', 'ui'):
            return jsonify({'status': 'error', 'message': 'Field "source": unknown value, should be either "node" or "ui"'}), 400

        # Token (for node)
        if data['source'] == 'node' and 'token' not in data:
            return jsonify({'status': 'error', 'message': 'Field "token" missing in payload (needed when source is "node")'}), 400

        # Data
        if 'data_to_update' not in data:
            return jsonify({'status': 'error', 'message': 'Field "data_to_update" missing in payload'}), 400

        if type(data['data_to_update']) != dict:
            return jsonify({'status': 'error', 'message': 'Field "data_to_update": should be a dict'}), 400

        if 'status' in data['data_to_update'] and data['data_to_update']['status'] not in ('free', 'reserved', 'waiting_for_authentication', 'occupied', 'violation', 'unauthorized'):
            return jsonify({'status': 'error', 'message': 'Field "status": must be in ("free", "reserved", "waiting_for_authentication", "occupied", "violation", "unauthorized")'}), 400

        #---Authenticate the source
        #-Node
        if data['source'] == 'node':
            # Authentication
            if not authenticate_node(current_app.config['DB_SERVICE'], node_id, data['token']):
                return jsonify({'status': 'auth_err', 'message': 'Authentication failed! Wrong node secret token'}), 403

            source = 'node'

        #-UI
        else:
            try:
                payload = decode_token()

            except ValueError as err:
                return jsonify({'status': 'auth_err', 'message': str(err)}), 401

            source = 'admin' if payload['is_admin'] else 'user'

        #---Check data to update and corresponding permissions
        # Init
        request_data_to_update = data['data_to_update'] # Dict of data to modify, shaped as received
        update_data = {} # The dict that will contain the new content (only modified parts) shaped as in the DB.

        # Handle 'profile' and 'used_by' updates
        for keyword in ('profile', 'used_by'):
            if keyword in request_data_to_update:
                if source != 'admin':
                    return jsonify({'status': 'perm_err', 'message': f'Not allowed to edit "{keyword}"'}), 403
                else:
                    update_data[keyword] = request_data_to_update[keyword]

        # Handle 'status' update
        if 'status' in request_data_to_update:
            new_status = request_data_to_update['status']

            if source == 'user':
                if new_status == 'reserved': # Try to make the reservation
                    if not node_management.reserve(payload['uid']):
                        return jsonify({'status': 'reservation_error', 'message': 'Error while taking the reservation'}), 400

                elif new_status == 'free': # Cancel the reservation
                    if not node_management.cancel_reservation(payload['uid']):
                        return jsonify({'status': 'reservation_error', 'message': 'Error while cancelling the reservation'}), 400

                else:
                    return jsonify({'status': 'perm_err', 'message': 'User can only (try to) change node status to "reserved", or "free" (to cancel reservation)'}), 403 

            elif source == 'node':
                node_management.new_status_from_node(new_status) # Handle actions to perform with new status

            # Update status
            update_data['data'] = {'status': new_status}

        # Update in database
        node_management.update_content(update_data)

        return jsonify({'status': 'success', 'message': 'node updated successfully'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@nodes_api.route("/<node_id>", methods=['DELETE'])
@token_required(only_admins=True)
def delete_node(node_id):
    '''Deletes a node.'''

    try:
        # Find node
        node = current_app.config['DB_SERVICE'].get_dr('node', node_id)
        if not node:
            return jsonify({'status': 'error', 'message': 'node not found'}), 404

        # If node is used by a user, update the corresponding user
        if node['used_by'] != '':
            user_checker = UserCheck(current_app.config['DB_SERVICE'], node['used_by'])

            if user_checker.is_uid_valid():
                if user_checker.get_nb_reservations() == 1: # It is a reservation
                    user_checker.decrease_nb_reservations()

                elif user_checker.get()['is_parked']: # The user is parked on the node
                    user_checker.update_content({'is_parked': False})

        # Delete node
        current_app.config['DB_SERVICE'].delete_dr('node', node_id)

        return jsonify({'status': 'success', 'message': 'node deleted successfully'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
