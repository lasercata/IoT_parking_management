#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for
from flask_bcrypt import Bcrypt
import jwt
from datetime import datetime, timedelta, timezone
import requests
import os
from sys import argv

##-Init
app = Flask(__name__)
bcrypt = Bcrypt(app)

# Secret key for JWT
# IMPORTANT: use the same secret key as in the backend
app.config['SECRET_KEY'] = 'your-shared-secret-key' #TODO: use .env

# Base URL of the IoT platform
PLATFORM_URL = 'https://localhost:5000' #TODO: use .env

#TODO: connect to the DB
# Simulated user store (replace with database in real-world scenario)
USERS = {
    'admin': {
        'uid': '0',
        'is_admin': True,
        'password': bcrypt.generate_password_hash('azer').decode('utf-8')
    },
    'usr1': {
        'uid': '39ac70e4',
        'is_admin': False,
        'password': bcrypt.generate_password_hash('azer').decode('utf-8')
    },
    'usr2': {
        'uid': '1c25d917',
        'is_admin': False,
        'password': bcrypt.generate_password_hash('azer').decode('utf-8')
    }
}

##-JWT Token functions (authentication)
def generate_token(username: str, uid: str, is_admin: bool) -> str:
    '''Generate a JWT token for the given user that expires after one day.'''

    payload = {
        'uid': uid,
        'username': username,
        'is_admin': is_admin,
        'exp': datetime.now(timezone.utc) + timedelta(days=1) # Token expires after one day
    }

    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token) -> tuple[str, str] | None:
    '''
    Verify and decode JWT token.

    Out:
        None if error
        (username, is_admin) from the token otherwise
    '''

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['username'], payload['is_admin']

    except jwt.ExpiredSignatureError:
        return None

    except jwt.InvalidTokenError:
        return None

##-Routes
@app.route('/')
def home():
    '''
    Home page.
    Access restricted to logged users.
    '''

    token = request.cookies.get('token')
    tk_data = verify_token(token)

    if tk_data is None:
        return redirect(url_for('login'))
    
    username, is_admin = tk_data

    if is_admin:
        return render_template('home_admin.html', username=username)
    else:
        return render_template('home.html', username=username)

@app.route('/reservation_page')
def reservation_page():
    '''
    Fetch nodes from IoT platform API and load the user reservation page
    Access restricted to logged users.
    '''

    token = request.cookies.get('token')
    if token is None:
        return jsonify({'error': 'No authentication token'}), 401
    
    try:
        # Make request to IoT platform API
        response = requests.get(
            f'{PLATFORM_URL}/nodes?status=free',
            headers={'Authorization': f'Bearer {token}'}
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
def nodes_page():
    '''
    Fetch nodes from IoT platform API.
    Access restricted to admins.
    '''

    # Check that there is a token, and that it is an admin one
    token = request.cookies.get('token')
    if token is None:
        return jsonify({'error': 'No authentication token'}), 401

    tk_data = verify_token(token)
    if tk_data is None:
        return jsonify({'error': 'No authentication token'}), 401
    
    _, is_admin = tk_data
    if not is_admin:
        return jsonify({'error': 'Not authorized to access this page'}), 401
    
    try:
        # Make request to IoT platform API
        response = requests.get(
            f'{PLATFORM_URL}/nodes?status=free',
            headers={'Authorization': f'Bearer {token}'}
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
def users_page():
    '''
    Fetch users from IoT platform API.
    Access restricted to admin.
    '''

    # Check that there is a token, and that it is an admin one
    token = request.cookies.get('token')
    if token is None:
        return jsonify({'error': 'No authentication token'}), 401

    tk_data = verify_token(token)
    if tk_data is None:
        return jsonify({'error': 'No authentication token'}), 401
    
    _, is_admin = tk_data
    if not is_admin:
        return jsonify({'error': 'Not authorized to access this page'}), 401
    
    if not token:
        return jsonify({'error': 'No authentication token'}), 401
    
    try:
        # Make request to IoT platform API
        response = requests.get(
            f'{PLATFORM_URL}/users',
            headers={'Authorization': f'Bearer {token}'}
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
    '''Login route handling both GET and POST requests.'''

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if user exists and password is correct
        if username in USERS and bcrypt.check_password_hash(USERS[username]['password'], password):
            usr = USERS[username]
            token = generate_token(username, usr['uid'], usr['is_admin'])
            
            # Create response with token as cookie
            response = make_response(redirect(url_for('home')))
            response.set_cookie('token', token, httponly=True, secure=True, samesite='Strict')
            
            return response
        
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    '''Logout route to clear token.'''

    response = make_response(redirect(url_for('login')))
    response.delete_cookie('token')
    return response

if __name__ == '__main__':
    if len(argv) > 1:
        port = int(argv[1])
    else:
        port = 3000

    app.run(debug=True, port=port)
