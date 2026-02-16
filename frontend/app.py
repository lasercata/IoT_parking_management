#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for
from flask_bcrypt import Bcrypt
import requests
from sys import argv

import re # To check email

from src.load_config import get_db_service, get_vars
from src.authentication import TokenManager, token_required, UserAuthentication

##-Init
app = Flask(__name__)
bcrypt = Bcrypt(app)

var_dict = get_vars()
SECRET_KEY = var_dict['SECRET_KEY']
PLATFORM_URL = var_dict['PLATFORM_URL']

db_service = get_db_service()

app.config['SECRET_KEY'] = SECRET_KEY

token_manager = TokenManager(SECRET_KEY)
user_authentication = UserAuthentication(db_service, bcrypt, token_manager, PLATFORM_URL)


##-Utils
def is_valid_email(email: str) -> bool:
    '''Checks if the `email` is a valid one'''

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    return re.match(pattern, email) is not None


##-Routes
@app.route('/')
def home():
    '''
    Home page.
    Access restricted to logged users.
    '''

    # If not logged in, redirect to login page
    try:
        token = token_manager.retrieve_token('cookies')
    except RuntimeError:
        return redirect(url_for('login'))

    # If comming from pwd_reset page and logged in, it means that the password has been changed.
    src = request.args.get('src')
    info = 'Password changed successfully!' if src == 'pwd_reset' else ''

    # Get token
    tk_payload = token_manager.decode_token(token)

    # Get user data from the platform
    response = requests.get(
        f'{PLATFORM_URL}/api/users/{tk_payload["uid"]}',
        headers={'Authorization': token}
    )

    if response.status_code == 404: # Unknown user. Probably deleted
        return redirect(url_for('logout'))
    
    if response.status_code != 200:
        return jsonify(response.json()), response.status_code

    user_data = response.json()

    # Render a different page for admin or user
    if token_manager.is_admin(token):
        # For admin, also calculate the number of nodes and of users
        response_nodes = requests.get(
            f'{PLATFORM_URL}/api/nodes/',
            headers={'Authorization': token}
        )
        if response_nodes.status_code == 200:
            nb_nodes = len(response_nodes.json()['nodes'])
        else:
            nb_nodes = 'error'

        response_users = requests.get(
            f'{PLATFORM_URL}/api/users/',
            headers={'Authorization': token}
        )
        if response_users.status_code == 200:
            nb_users = len(response_users.json()['users'])
        else:
            nb_users = 'error'

        return render_template('home_admin.html', username=tk_payload['username'], user_data=user_data, nb_nodes=nb_nodes, nb_users=nb_users, info=info)

    else:
        return render_template('home_user.html', username=tk_payload['username'], user_data=user_data, info=info)

@app.route('/reservation_page', methods=['GET', 'POST'])
@token_required(SECRET_KEY)
def reservation_page():
    '''
    Fetch nodes from IoT platform API and load the user reservation page
    Access restricted to logged users.

    GET: render the HTML page
    POST: make/cancel a reservation

    For POST, the payload should have the form:
    {
        "action": str,   # "reserve" | "cancel"
        "node_id": str   # the id of the concerned node
    }
    '''

    if request.method == 'GET':
        try:
            token = token_manager.retrieve_token('cookies')

            # Request free nodes to IoT platform API
            response_1 = requests.get(
                f'{PLATFORM_URL}/api/nodes?status=free',
                headers={'Authorization': token}
            )

            # Request nodes reserved by the user IoT platform API
            response_2 = requests.get(
                f'{PLATFORM_URL}/api/nodes?status=reserved&used_by_me',
                headers={'Authorization': token}
            )
            
            # Check response from IoT platform
            if response_1.status_code == 200 and response_2.status_code == 200:
                free_nodes = response_1.json()
                reserved_nodes = response_2.json()

                return render_template(
                    'reservation_page.html',
                    free_nodes=free_nodes,
                    reserved_nodes=reserved_nodes
                )
            else:
                # Handle authentication or other errors
                c1, c2 = response_1.status_code, response_2.status_code
                c = c1 if c1 != 200 else c2

                return jsonify({'error': 'Failed to fetch nodes'}), c
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # POST
    else:
        try:
            # First, check payload format
            data = request.get_json()

            if 'action' not in data:
                return jsonify({'status': 'error', 'message': 'missing field "action"'}), 400
            if data['action'] not in ('reserve', 'cancel'):
                return jsonify({'status': 'error', 'message': 'field "action": should be either "reserve" or "cancel"'}), 400

            if 'node_id' not in data:
                return jsonify({'status': 'error', 'message': 'missing field "node_id"'}), 400
    
            # Prepare the request
            token = token_manager.retrieve_token('cookies')

            payload = {
                "data_to_update": {
                    "status": 'reserved' if data['action'] == 'reserve' else 'free'
                },
                "source": 'ui'
            }

            # Make request to IoT platform API
            response = requests.patch(
                f'{PLATFORM_URL}/api/nodes/{data["node_id"]}',
                headers={'Authorization': token, 'Content-Type': 'application/json'},
                json=payload
            )
            
            # Check response from IoT platform
            if response.status_code == 200:
                nodes = response.json()
                return jsonify({'status': 'success', 'message': 'node successfully updated'}), 200
            else:
                return jsonify(response.json()), response.status_code
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/nodes_page', methods=['GET', 'POST'])
@token_required(SECRET_KEY, only_admins=True)
def nodes_page():
    '''
    Fetch nodes from IoT platform API.
    Access restricted to admins.

    GET: render the HTML page
    POST: create/delete a node

    For POST, the payload should have the form:
    {
        "action": str,      # "delete" | "create"
        "node_data": json   # the data of the node. See below
    }

    If "action" is delete, "node_data" should have the following shape:
    "node_data": {
        "node_id": str
    }

    Otherwise, for node creation:
    "node_data": {
        "node_id": str,
        "profile": {
            "position": str,
            "token": str
        }
    }
    '''

    if request.method == 'GET':
        try:
            token = token_manager.retrieve_token('cookies')

            # Request nodes to IoT platform API
            response = requests.get(
                f'{PLATFORM_URL}/api/nodes/',
                headers={'Authorization': token}
            )
            
            # Check response from IoT platform
            if response.status_code == 200:
                nodes = response.json()
                return render_template('nodes_page.html', nodes=nodes)
            else:
                # Handle authentication or other errors
                return jsonify({'error': 'Failed to fetch nodes'}), response.status_code
        
        except requests.RequestException as e:
            return jsonify({'error': str(e)}), 500

    # POST
    else:
        try:
            # First, check payload format
            data = request.get_json()

            if 'action' not in data:
                return jsonify({'status': 'error', 'message': 'missing field "action"'}), 400
            if data['action'] not in ('delete', 'create'):
                return jsonify({'status': 'error', 'message': 'field "action": should be either "delete" or "create"'}), 400

            if 'node_data' not in data:
                return jsonify({'status': 'error', 'message': 'missing field "node_data"'}), 400
            if 'node_id' not in data['node_data']:
                return jsonify({'status': 'error', 'message': 'missing field "node_data.node_id"'}), 400
            if data['node_data']['node_id'] == '':
                return jsonify({'status': 'error', 'message': 'field "node_data.node_id" cannot be empty'}), 400

            if data['action'] == 'create':
                if 'profile' not in data['node_data']:
                    return jsonify({'status': 'error', 'message': 'missing field "node_data.profile" (for creation)'}), 400
                if 'position' not in data['node_data']['profile']:
                    return jsonify({'status': 'error', 'message': 'missing field "node_data.profile.position" (for creation)'}), 400
                if 'token' not in data['node_data']['profile']:
                    return jsonify({'status': 'error', 'message': 'missing field "node_data.profile.token" (for creation)'}), 400

            # Prepare the request for the platform
            token = token_manager.retrieve_token('cookies')

            # Make the action
            if data['action'] == 'delete':
                response = requests.delete(
                    f'{PLATFORM_URL}/api/nodes/{data["node_data"]["node_id"]}',
                    headers={'Authorization': token}
                )
                
                # Check response from IoT platform
                if response.status_code == 200:
                    return jsonify({'status': 'success', 'message': 'node successfully deleted'}), 200
                else:
                    return jsonify(response.json()), response.status_code

            else:
                payload = {
                    "_id": data['node_data']['node_id'],
                    "profile": data['node_data']['profile']
                }

                response = requests.post(
                    f'{PLATFORM_URL}/api/nodes/',
                    headers={'Authorization': token, 'Content-Type': 'application/json'},
                    json=payload
                )
                
                # Check response from IoT platform
                if response.status_code == 200:
                    return jsonify({'status': 'success', 'message': 'node successfully created'}), 201
                else:
                    return jsonify(response.json()), response.status_code
        
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/users_page', methods=['GET', 'POST'])
@token_required(SECRET_KEY, only_admins=True)
def users_page():
    '''
    Fetch users from IoT platform API.
    Access restricted to admin.

    GET: render the HTML page
    POST: create/delete a user

    For POST, the payload should have the form:
    {
        "action": str,      # "delete" | "create"
        "user_data": json   # the data of the user. See below
    }

    If "action" is delete, "user_data" should have the following shape:
    "user_data": {
        "user_id": str
    }

    Otherwise, for user creation:
    "user_data": {
        "user_id": str,
        "profile": {
            "username": str,
            "email": str,
            "is_admin": bool,
            "badge_expiration": date
        }
    }

    Note: it is prevented to delete its own account.
    '''
    
    if request.method == 'GET':
        try:
            token = token_manager.retrieve_token('cookies')

            # Make request to IoT platform API
            response = requests.get(
                f'{PLATFORM_URL}/api/users',
                headers={'Authorization': token}
            )
            
            # Check response from IoT platform
            if response.status_code == 200:
                users = response.json()
                return render_template('users_page.html', users=users)
            else:
                # Handle authentication or other errors
                return jsonify({'error': 'Failed to fetch users'}), response.status_code
        
        except requests.RequestException as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # POST
    else:
        try:
            # First, check payload format
            data = request.get_json()

            if 'action' not in data:
                return jsonify({'status': 'error', 'message': 'missing field "action"'}), 400
            if data['action'] not in ('delete', 'create'):
                return jsonify({'status': 'error', 'message': 'field "action": should be either "delete" or "create"'}), 400

            if 'user_data' not in data:
                return jsonify({'status': 'error', 'message': 'missing field "user_data"'}), 400
            if 'user_id' not in data['user_data']:
                return jsonify({'status': 'error', 'message': 'missing field "user_data.user_id"'}), 400
            if data['user_data']['user_id'] == '':
                return jsonify({'status': 'error', 'message': 'field "user_data.user_id" cannot be empty'}), 400

            if data['action'] == 'create':
                if 'profile' not in data['user_data']:
                    return jsonify({'status': 'error', 'message': 'missing field "user_data.profile" (for creation)'}), 400

                for field in {'username', 'email', 'is_admin', 'badge_expiration'}:
                    if field not in data['user_data']['profile']:
                        return jsonify({'status': 'error', 'message': f'missing field "user_data.profile.{field}" (for creation)'}), 400

                if not is_valid_email(data['user_data']['profile']['email']):
                    return jsonify({'status': 'error', 'message': 'Invalid email'}), 400

            # Prepare the request for the platform
            token = token_manager.retrieve_token('cookies')

            # Make the action
            if data['action'] == 'delete':
                # Check that the admin is not deleting its own account
                if token_manager.decode_token(token)['uid'] == data['user_data']['user_id']:
                    return jsonify({'status': 'error', 'message': 'You cannot delete your own account'}), 401

                # Delete account
                response = requests.delete(
                    f'{PLATFORM_URL}/api/users/{data["user_data"]["user_id"]}',
                    headers={'Authorization': token}
                )
                
                # Check response from IoT platform
                if response.status_code == 200:
                    return jsonify({'status': 'success', 'message': 'user successfully deleted'}), 200
                else:
                    return jsonify(response.json()), response.status_code

            else:
                payload = {
                    "_id": data['user_data']['user_id'],
                    "profile": data['user_data']['profile']
                }

                response = requests.post(
                    f'{PLATFORM_URL}/api/users/',
                    headers={'Authorization': token, 'Content-Type': 'application/json'},
                    json=payload
                )
                
                # Check response from IoT platform
                if response.status_code == 200:
                    return jsonify({'status': 'success', 'message': 'user successfully created'}), 201
                else:
                    return jsonify(response.json()), response.status_code
        
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    '''
    Login route handling both GET and POST requests.

    GET: serve the HTML page
    POST: try to log in
    '''

    if request.method == 'GET':
        src = request.args.get('src')

        try:
            token = token_manager.retrieve_token('cookies') # Check if token is present

        except RuntimeError: # No token -> go to login
            if src == 'pwd_reset':
                return render_template('login.html', info='Password successfully changed. Please log in')
            else:
                return render_template('login.html')

        else: # token found -> go to home page
            if src == 'pwd_reset':
                return redirect(url_for('home', src='pwd_reset'))
            else:
                return redirect(url_for('home'))
    
    # POST
    else:
        username = request.form['username']
        password = request.form['password']
        
        # Check if user exists and password is correct
        # if username in USERS and bcrypt.check_password_hash(USERS[username]['password'], password):
        token = user_authentication.test_credentials(username, password)

        if token is None:
            return render_template('login.html', error='Invalid credentials')

        # Create response with token as cookie
        response = make_response(redirect(url_for('home')))
        response.set_cookie('token', token, httponly=True, secure=True, samesite='Strict')
        
        return response

@app.route('/pwd_reset', methods=['GET', 'POST'])
def pwd_reset():
    '''
    Password reset route handling both GET and POST requests.

    GET: serve the HTML page
    POST: send the new password
    '''


    if request.method == 'GET':
        return render_template('pwd_reset.html')

    # POST
    else:
        username = request.form['username']
        pwd_reset_tk = request.form['pwd_reset_tk']
        new_pwd = request.form['password']
        pwd_repeat = request.form['password_2']

        if new_pwd != pwd_repeat:
            return render_template('pwd_reset.html', error='Passwords do not correspond')
        
        try:
            response = user_authentication.set_new_password(username, new_pwd, pwd_reset_tk)

            if response.ok:
                return redirect(url_for('login', src='pwd_reset'))
                # return render_template('login.html', info='Password updated. Please login')
            else:
                return render_template('pwd_reset.html', error='Something went wrong. Please retry later')

        except RuntimeError: # User not found
            return render_template('pwd_reset.html', error='Wrong username')

        except ValueError: # Wrong code
            return render_template('pwd_reset.html', error='Wrong username or code')

@app.route('/send_pwd_reset')
@token_required(SECRET_KEY)
def send_pwd_reset():
    '''Sends a request to the backend to send an email to the user in order to change its password'''

    token = token_manager.retrieve_token('cookies')

    # Send new password
    response = requests.get(
        f'{PLATFORM_URL}/api/users/pwd_reset',
        headers={'Authorization': token}
    )

    return redirect(url_for('pwd_reset'))

@app.route('/logout')
def logout():
    '''Logout route to clear token.'''

    response = make_response(redirect(url_for('login')))
    response.delete_cookie('token')
    return response

@app.route('/not_allowed')
def not_allowed():
    '''Route for not allowed page'''

    return render_template('not_allowed.html')

@app.route('/invalid_token')
def invalid_token():
    '''Route for invalid token'''

    return render_template('invalid_token.html')

##-Run
if __name__ == '__main__':
    if len(argv) > 1:
        port = int(argv[1])
    else:
        port = 3000

    app.run(debug=True, port=port)
