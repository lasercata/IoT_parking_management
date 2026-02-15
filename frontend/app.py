#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for
from flask_bcrypt import Bcrypt
import requests
from sys import argv

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

#TODO: connect to the DB
# Simulated user store (replace with database in real-world scenario)
USERS = {
    'admin': {
        'uid': '0',
        'is_admin': True,
        'password': bcrypt.generate_password_hash('azer').decode('utf-8')
    },
    'usr1': {
        'uid': 'DEADBEEF',
        'is_admin': False,
        'password': bcrypt.generate_password_hash('azer').decode('utf-8')
    },
    'usr2': {
        'uid': '1c25d917',
        'is_admin': False,
        'password': bcrypt.generate_password_hash('azer').decode('utf-8')
    }
}

##-Routes
@app.route('/')
def home():
    '''
    Home page.
    Access restricted to logged users.
    '''

    try:
        token = token_manager.retrieve_token('cookies')
    except RuntimeError:
        return redirect(url_for('login'))

    src = request.args.get('src')
    info = 'Password changed successfully!' if src == 'pwd_reset' else ''

    tk_payload = token_manager.decode_token(token)

    if token_manager.is_admin(token):
        return render_template('home_admin.html', username=tk_payload['username'], info=info)

    else:
        return render_template('home.html', username=tk_payload['username'], info=info)

@app.route('/reservation_page')
@token_required(SECRET_KEY)
def reservation_page():
    '''
    Fetch nodes from IoT platform API and load the user reservation page
    Access restricted to logged users.
    '''

    try:
        token = token_manager.retrieve_token('cookies')

        # Make request to IoT platform API
        response = requests.get(
            f'{PLATFORM_URL}/api/nodes?status=free',
            headers={'Authorization': token}
        )
        
        # Check response from IoT platform
        if response.status_code == 200:
            nodes = response.json()
            return render_template('reservation_page.html', nodes=nodes)
        else:
            # Handle authentication or other errors
            return jsonify({'error': 'Failed to fetch nodes'}), response.status_code
    
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/nodes_page')
@token_required(SECRET_KEY, only_admins=True)
def nodes_page():
    '''
    Fetch nodes from IoT platform API.
    Access restricted to admins.
    '''

    try:
        token = token_manager.retrieve_token('cookies')

        # Make request to IoT platform API
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

@app.route('/users_page')
@token_required(SECRET_KEY, only_admins=True)
def users_page():
    '''
    Fetch users from IoT platform API.
    Access restricted to admin.
    '''
    
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
        return jsonify({'error': str(e)}), 500

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
