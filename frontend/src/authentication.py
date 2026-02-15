#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Handles API authentication with JWT tokens and user authentication'''

##-Imports
from typing import Any
from flask_bcrypt import Bcrypt
from flask import request, redirect, url_for
import jwt
import requests
from datetime import datetime, timedelta, timezone
from functools import wraps

from src.database import DatabaseService

##-JWT Token manger
class TokenManager:
    '''Manages JWT tokens'''

    def __init__(self, secret_key: str):
        '''
        Initiates the class

        In:
            - secret_key: the JWT secret key (shared with the platform)
        '''

        self._secret_key = secret_key

    def generate_token(self, username: str, uid: str, is_admin: bool, duration: timedelta = timedelta(days=1)) -> str:
        '''Generates a JWT token for the given user that expires after 24 hours.'''

        payload = {
            'uid': uid,
            'username': username,
            'is_admin': is_admin,
            'exp': datetime.now(timezone.utc) + duration
        }

        return jwt.encode(payload, self._secret_key, algorithm='HS256')

    def decode_token(self, token: str) -> dict[str, Any]:
        '''
        Tries to decode the token and return its content.

        Out:
            payload     if successful
            ValueError  Otherwise
        '''

        try:
            # Decode the token
            payload = jwt.decode(token, self._secret_key, algorithms=['HS256'])
            return payload

        except jwt.ExpiredSignatureError:
            raise ValueError('Token has expired!')

        except jwt.InvalidTokenError:
            raise ValueError('Invalid token!')

    def is_admin(self, token: str) -> bool:
        '''
        Tries to decode the token (using `self.decode_token`) and checks if it is from an admin.

        Out:
            True       if token is owned by an admin
            False      if not
            ValueError if error while decoding
        '''

        token_payload = self.decode_token(token)
        return token_payload['is_admin']

    def retrieve_token(self, source: str) -> str:
        '''
        Tries to retrieve the token from `source`.

        In:
            - source: the source of the token. Should be in:
                + 'cookies': retrieve from cookies;
                + 'headers': retrieve from headers;
                + 'first': try cookies, and then headers if not found

        Out:
            str: the token

        Raises:
            ValueError   if `source` not in options
            RuntimeError if token not found
        '''

        if source not in {'cookies', 'headers', 'first'}:
            raise ValueError('Argument "source" not correct')

        token = None

        if source in ('cookies', 'first'):
            token = request.cookies.get('token')

            if token is not None:
                return token

        if source in ('headers', 'first'):
            if 'Authorization' in request.headers:
                return request.headers['Authorization']

        raise RuntimeError('token not found')

##-Decorator (JWT)
def token_required(secret_key: str, only_admins: bool = False):
    '''
    Creates a decorator that ensure that the connected user possesses a valid token.

    In:
        - only_admins: if True, restrict access only to admins. Otherwise, restrict access to token bearers.
    '''

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token_manager = TokenManager(secret_key)

            try:
                token = token_manager.retrieve_token(source='first')
                payload = token_manager.decode_token(token)

            except (ValueError, RuntimeError) as err:
                # return render_template('login.html', error=str(err))
                return redirect(url_for('invalid_token'))

            # Privilege check
            if only_admins and not payload['is_admin']:
                # return '', 403
                # return render_template('login.html', error='Only admins can access this resource')
                return redirect(url_for('not_allowed'))

            # If we get here, token is valid
            return f(*args, **kwargs)
        
        return decorated

    return decorator

##-User authentication
class UserAuthentication:
    '''Manages the authentication of end users (username, password)'''

    def __init__(self, db_service: DatabaseService, bcrypt: Bcrypt, token_manager: TokenManager, platform_url: str):
        '''
        Initiates the class

        In:
            - db_service: the database controller
            - bcrypt: the initialized bcrypt object
            - token_manager: the token manager
            - platform_url: the base URL of the platform
        '''

        self._db_service = db_service
        self._bcrypt = bcrypt
        self._token_manager = token_manager
        self._platform_url = platform_url

    def test_credentials(self, username: str, password: str, token_duration: timedelta = timedelta(days=1)) -> str | None:
        '''
        Checks if the credentials (username, password) are correct.
        If so, generate a token.

        In:
            - username: the received username
            - password: the received password
            - token_duration: the duration of the token to generate (used if credentials are correct)

        Out:
            str: token    if credentials are correct
            None          otherwise
        '''
    
        user = self._db_service.get_user_by_username(username)

        if user is None:
            return

        pwd_hash_db = user['pwd_hash']

        if self._bcrypt.check_password_hash(pwd_hash_db, password):
            return self._token_manager.generate_token(username, user['_id'], user['profile']['is_admin'], token_duration)

    def set_new_password(self, username: str, new_password: str, pwd_reset_tk: str) -> requests.Response:
        '''
        Sends the new password to the platform for it to write it in the database.

        In:
            - username: the username of the concerned user
            - new_password: the new password, in clear
            - pwd_reset_tk: the code received by email

        Out:
            requests.Respons: the response of the platform

        Raises:
            RuntimeError if user not found
            ValueError   if pwd_reset_tk is incorrect
        '''
    
        # Check user existance
        user = self._db_service.get_user_by_username(username)
        if user is None:
            raise RuntimeError('user not found')

        # Check if pwd_reset_tk is correct
        if pwd_reset_tk != user['pwd_reset_tk']:
            raise ValueError('Password reset token is invalid')

        # Make payload
        payload = {
            'pwd_hash': self._bcrypt.generate_password_hash(new_password).decode('utf-8'),
            'pwd_reset_tk': pwd_reset_tk
        }

        user_id = user['_id']

        # Make a token
        token = self._token_manager.generate_token(username, user_id, False, duration=timedelta(minutes=1))

        # Send new password
        response = requests.patch(
            f'{self._platform_url}/api/users/{user_id}',
            headers={'Authorization': token, 'Content-Type': 'application/json'},
            json=payload
        )

        return response
        
