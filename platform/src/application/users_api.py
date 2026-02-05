from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.virtualization.digital_replica.dr_factory import DRFactory

users_api = Blueprint('users_api', __name__,url_prefix = '/api/users')

def register_user_blueprint(app):
    app.register_blueprint(users_api)

@users_api.route('/', methods=['GET'])
def list_users(): #TODO: restrict to admin
    '''
    Get all users with optional filtering.

    Filters on:
        - is_admin (bool)
        - is_parked (bool)
        - is_disabled (bool)
    '''

    try:
        filters = {}
        for filter_name in ('is_parked', 'is_disabled'):
            f = request.args.get(filter_name)
            if f:
                filters[f'{filter_name}'] = f.lower() == 'true'

        f = request.args.get('is_admin')
        if f:
            filters['profile.is_admin'] = f.lower() == 'true'

        print(filters)

        users = current_app.config["DB_SERVICE"].query_drs('user', filters)
        return jsonify({"users": users}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@users_api.route('/', methods=['POST'])
def create_user(): #TODO: restrict to admin
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
def get_user(user_id): #TODO: restrict to admin
    '''Gets user details'''

    try:
        user = current_app.config["DB_SERVICE"].get_dr("user", user_id)
        if not user:
            return jsonify({"error": "user not found"}), 404

        return jsonify(user), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@users_api.route("/<user_id>", methods=['PATCH'])
def update_user(user_id):
    '''
    Updates user details.

    Usages:
        - By user itself:
            + change password

        - By admin:
            + change is_disabled, is_admin, email
    '''

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
