from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.virtualization.digital_replica.dr_factory import DRFactory
from src.application.authentication import decode_token, token_required

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
def update_user(user_id): #TODO
    '''
    Updates user details.

    Usages:
        - By user itself:
            + change password

        - By admin:
            + change violation_detected, is_admin, email
    '''

    token_payload = decode_token()

    if user_id != token_payload['uid']:
        return jsonify({'message', 'Impossible to edit an other user'}), 401

    raise NotImplementedError('TODO')

    try:
        data = request.get_json()
        update_data = {}

        #Handle profile updates
        if "profile" in data:
            update_data["profile"] = data["profile"]

        #Handle data updates
        if "data" in data:
            update_data["data"] = data["data"]

        #Always update the 'updated at' timestamp
        update_data["metadata"] = {"updated_at":datetime.utcnow()}

        current_app.config["DB_SERVICE"].update_dr("user",user_id,update_data)
        return jsonify({"status": "success", "message": "user updated successfully"}), 200

    except Exception as e:
        return jsonify({"error":str(e)}),500

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
