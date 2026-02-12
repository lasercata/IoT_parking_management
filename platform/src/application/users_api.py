from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.application.user_management import UserCheck
from src.virtualization.digital_replica.dr_factory import DRFactory
from src.application.authentication import decode_token, is_admin, token_required

users_api = Blueprint('users_api', __name__,url_prefix = '/api/users')

def register_user_blueprint(app):
    app.register_blueprint(users_api)

@users_api.route('/', methods=['GET'])
@token_required(only_admins=True)
def list_users():
    '''
    Get all users with optional filtering.

    Filters on:
        - is_admin (bool)
        - is_parked (bool)
        - violation_detected (bool)
    '''

    try:
        filters = {}
        for filter_name in ('is_parked', 'violation_detected'):
            f = request.args.get(filter_name)
            if f:
                filters[f'{filter_name}'] = f.lower() == 'true'

        f = request.args.get('is_admin')
        if f:
            filters['profile.is_admin'] = f.lower() == 'true'

        users = current_app.config["DB_SERVICE"].query_drs('user', filters)
        return jsonify({"users": users}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@users_api.route('/', methods=['POST'])
@token_required(only_admins=True)
def create_user():
    '''
    Creates a new user.

    Data to post:
    {
        "_id": str,     # The UID of the RFID tag
        "profile": {
            "username": str,
            "email": str,
            "is_admin": bool
        }
    }
    '''

    try:
        data = request.get_json()
        dr_factory = DRFactory("src/virtualization/templates/user.yaml")
        user = dr_factory.create_dr('user', data)
        user_id = current_app.config["DB_SERVICE"].save_dr("user", user)

        #TODO: create a password init link
        # Return the link
        # And email it to the user

        return jsonify({"status": "success", "message": "user created successfully", "user_id": user_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@users_api.route("/<user_id>", methods=['GET'])
@token_required(only_admins=True)
def get_user(user_id):
    '''Gets user details'''

    try:
        user = current_app.config["DB_SERVICE"].get_dr("user", user_id)
        if not user:
            return jsonify({"error": "user not found"}), 404

        return jsonify(user), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@users_api.route("/<user_id>", methods=['PATCH'])
@token_required()
def update_user(user_id):
    '''
    Updates user details.

    Who can hit this endpoint?
        - user: change his password
        - admin: change (nearly) anything

    Note: the request for the user password change is proxied by the frontend server (that hashes the password before sending it here).

    User payload format (user changes its password):
    {
        "pwd_hash": str
    }

    Admin payload format:
    {
        "pwd_hash": str,       # Note that this is only allowed if the target user is the user sending the query (i.e admins cannot directly choose a password for a user)
        "auth_bytes": str,
        "first_connection": bool,
        "violation_detected": bool,
        "profile": {
            "badge_expiration": datetime,
            "email": str,
            "username": str,
            "is_admin": bool
        }
    }
    '''

    try:
        #---Check that node exists
        user_checker = UserCheck(current_app.config['DB_SERVICE'], user_id)
        if not user_checker.is_uid_valid():
            return jsonify({'status': 'error', 'message': 'user not found'}), 404

        #---Init
        data = request.get_json()

        #---Authorization
        token_uid = decode_token()['uid']

        if 'pwd_hash' in data:
            if user_id != token_uid:
                return jsonify({'status': 'error', 'message': 'Impossible to change the password of an other user'}), 403

        #---Select the data to update
        update_data = {}

        if is_admin():
            updatable_fiels = ('pwd_hash', 'auth_bytes', 'first_connection', 'violation_detected', 'profile')

            for field in updatable_fiels:
                if field in data:
                    update_data[field] = data[field]

        else:
            if 'pwd_hash' in data:
                update_data['pwd_hash'] = data['pwd_hash']

        user_checker.update_content(update_data)
        return jsonify({'status': 'success', 'message': 'user updated successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_api.route("/<user_id>", methods=['DELETE'])
@token_required(only_admins=True)
def delete_user(user_id):
    '''Deletes a user'''

    try:
        user = current_app.config["DB_SERVICE"].get_dr("user", user_id)

        if not user:
            return jsonify({"error": "user not found"}), 404

        current_app.config["DB_SERVICE"].delete_dr("user", user_id)

        return jsonify({"status": "success", "message": "user deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
