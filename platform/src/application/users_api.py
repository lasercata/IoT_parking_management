from flask import Blueprint, request, jsonify, current_app
from src.application.authentication import decode_token, is_admin, token_required
from src.application.user_management import UserCheck, AccountManagement

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
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        # Init
        data = request.get_json()

        if '_id' not in data:
            return jsonify({'status': 'error', 'message': 'malformed payload: missing field "_id"'}), 400

        user_id = data['_id']
        account_manager = AccountManagement(user_id, current_app.config['FRONTEND_URL'], current_app.config['DB_SERVICE'])

        try:
            pwd_reset_tk = account_manager.create(data)
            return jsonify({'status': 'success', 'message': 'user created successfully', 'user_id': user_id, 'pwd_reset_tk': pwd_reset_tk}), 201

        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@users_api.route("/<user_id>", methods=['GET'])
@token_required()
def get_user(user_id):
    '''
    Gets user details

    Authorization:
        - Admins can get any user, and receive the whole data in output ;
        - Users can only retrieve their data, and only selected fields.
    '''

    try:
        #---Check that user exists
        user_checker = UserCheck(current_app.config['DB_SERVICE'], user_id)
        if not user_checker.is_uid_valid():
            return jsonify({'status': 'error', 'message': 'user not found'}), 404

        #---Authorization
        token_uid = decode_token()['uid']

        if is_admin():
            return jsonify(user_checker.get()), 200

        else:
            if user_id != token_uid:
                return jsonify({'status': 'error', 'message': 'Impossible to get an other user'}), 403
            
            all_user_data = user_checker.get()

            user_data = {}
            user_data['profile'] = all_user_data['profile']
            user_data['violation_detected'] = all_user_data['violation_detected']
            user_data['is_parked'] = all_user_data['is_parked']
            user_data['nb_reservations'] = all_user_data['nb_reservations']

            return jsonify(user_data), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        "pwd_hash": str,
        "pwd_reset_tk": str    # Not to change; used to authentify the user
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
        #---Check that user exists
        user_checker = UserCheck(current_app.config['DB_SERVICE'], user_id)
        if not user_checker.is_uid_valid():
            return jsonify({'status': 'error', 'message': 'user not found'}), 404

        #---Init
        data = request.get_json()

        #---Authorization
        token_uid = decode_token()['uid']

        if 'pwd_hash' in data:
            # Check that it is the same user
            if user_id != token_uid:
                return jsonify({'status': 'error', 'message': 'Impossible to change the password of an other user'}), 403

            # Check the password reset token
            pwd_reset_tk__from_db = user_checker.get()['pwd_reset_tk']

            if pwd_reset_tk__from_db == '':
                return jsonify({'status': 'error', 'message': 'Password reset has not been asked.'}), 403

            if 'pwd_reset_tk' not in data:
                return jsonify({'status': 'error', 'message': 'Missing field "pwd_reset_tk" to change the password'}), 401

            if data['pwd_reset_tk'] != pwd_reset_tk__from_db:
                return jsonify({'status': 'error', 'message': 'Field "pwd_reset_tk" is incorrect'}), 401

            # All checks passed for password reset.
            # So deactivate the password reset (only usable once)
            user_checker.update_content({'pwd_reset_tk': ''})

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
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        return jsonify({'status': 'error', 'message': str(e)}), 500

@users_api.route("/pwd_reset", methods=['GET'])
@token_required()
def send_pwd_reset():
    '''Send a password reset link+code by email'''

    try:
        # Get user id (UID) from its token
        user_id = decode_token()['uid']

        # Check that user exists
        user = current_app.config['DB_SERVICE'].get_dr('user', user_id)
        if not user:
            return jsonify({'error': 'user not found'}), 404

        # Send email
        account_manager = AccountManagement(user_id, current_app.config['FRONTEND_URL'], current_app.config['DB_SERVICE'])
        account_manager.send_pwd_reset(creation=False)

        return jsonify({'status': 'success', 'message': 'email sent'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
