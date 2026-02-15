#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Handles authentication with JWT tokens'''

##-Imports
from typing import Any
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import render_template, request, redirect, url_for

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


    def generate_token(self, username: str, uid: str, is_admin: bool) -> str:
        '''Generates a JWT token for the given user that expires after 24 hours.'''

        payload = {
            'uid': uid,
            'username': username,
            'is_admin': is_admin,
            'exp': datetime.now(timezone.utc) + timedelta(days=1) # Token expires after one day
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

##-Decorator
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
