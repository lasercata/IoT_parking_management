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
    'usr': {
        'password': bcrypt.generate_password_hash('azer').decode('utf-8')
    }
}

##-JWT Token functions (authentication)
def generate_token(username) -> str: #TODO: change param
    '''Generate a JWT token.'''

    payload = { #TODO: add fields (role[admin|user], UID, ...)
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=1)
    }

    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    '''Verify and decode JWT token.'''

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['username'] #TODO: return UID and role?

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
    username = verify_token(token)

    #TODO: different template for admin/user?
    
    if not username:
        return redirect(url_for('login'))
    
    return render_template('home.html', username=username)

@app.route('/nodes_page')
def nodes_page():
    '''
    Fetch nodes from IoT platform API.
    Access restricted to logged users.
    '''

    token = request.cookies.get('token')
    
    if not token:
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

    token = request.cookies.get('token') #TODO: restrict to admins.
    
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
            token = generate_token(username)
            
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
