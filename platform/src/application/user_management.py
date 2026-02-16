#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Implements functions to manage user data'''

##-Imports
import secrets
from typing import Any
from datetime import datetime

from src.application.notification_handlers import Discorder, Emailer
from src.services.database_service import DatabaseService
from src.virtualization.digital_replica.dr_factory import DRFactory

##-User check
class UserCheck:
    '''Class handling user authentication and authorization verification'''

    def __init__(self, db_service: DatabaseService, uid: str):
        '''
        Initiates the class

        In:
            - db_service: the DB controller
            - uid: the UID of the user
        '''

        self._db_service = db_service
        self._uid = uid

        self._user: dict[str, str] | None = None # Will be set by self.is_uid_valid in order to minimise calls to the DB

    def is_uid_valid(self) -> bool:
        '''
        Checks if the UID is present in the database

        Out:
            True   if the user's UID is present in the DB
            False  otherwise
        '''
    
        self._user = self._db_service.get_dr('user', self._uid)
        return self._user is not None

    def get(self) -> dict:
        '''
        Gets the json representing the user from the database.

        :raise ValueError: if not found
        '''

        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        return self._user

    def update_content(self, update_data: dict):
        '''
        Updates the data of the user in the database.
        Does not perform any check.

        In:
            - update_data: the data to update, shaped as in the database.
        '''

        # Always update the 'updated at' time stamp
        update_data['metadata'] = {'updated_at': datetime.utcnow()}
    
        self._db_service.update_dr('user', self._uid, update_data)

    def is_authenticated(self, auth: str, new_auth: str) -> bool:
        '''
        Checks the authentication bytes from the RFID card.
        It also updates the AUTH_BYTES in the DB if the user is authenticated.

        In:
            - auth: the authentication bytes from the badge
            - new_auth: the freshly written authentication bytes by the node

        Out:
            True        if the user UID has the correct authentication bytes
            False       otherwise
            ValueError  if UID not in DB
        '''

        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        # If violation flag already raised, stop here
        if self._user['violation_detected']:
            return False

        # Check for authentication bytes and update them
        if self._user['auth_bytes'] == auth:
            self._db_service.update_dr('user', self._uid, {'auth_bytes': new_auth}) # Update the auth bytes
            return True

        else:
            self._db_service.update_dr('user', self._uid, {'violation_detected': True}) # Set the violation flag
            return False # It is the responsibility of the caller to call the authority notification method

    def is_authorized(self) -> bool:
        '''
        Checks that the user is authorized to park (checks the badge expiration date).

        Out:
            True        if the user is authorized (badge not yet expired)
            False       otherwise
            ValueError  if UID not in DB
        '''
    
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        return datetime.utcnow() <= self._user['profile']['badge_expiration']

    def is_already_parked(self) -> bool:
        '''
        Checks if the user is already parked somewhere else.

        Out:
            False       if the user is NOT already parked
            True        otherwise
            ValueError  if UID not in DB
        '''
    
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        return self._user['is_parked']

    def can_reserve(self) -> bool:
        '''
        Checks the current number of reservation of the user.
        Also check that the user is not currently parked.
        A user can have at most 1 reservation.

        Out:
            True        if the user has 0 reservation (he can reserve)
            False       otherwise
            ValueError  if UID not in DB
        '''
    
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        return self._user['nb_reservations'] == 0 and not self._user['is_parked']

    def get_nb_reservations(self) -> int:
        '''Retrieves the number of reservations from the database'''
    
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        return self._user['nb_reservations']

    def increase_nb_reservations(self):
        '''nb_reservations += 1 in database'''
    
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        self.update_content({'nb_reservations': self.get_nb_reservations() + 1})

    def decrease_nb_reservations(self):
        '''nb_reservations -= 1 in database'''
    
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        self.update_content({'nb_reservations': self.get_nb_reservations() - 1})

    def send_cloning_event(self, node_id: str):
        '''
        Called when cloning is detected.

        Sends notification to authorities and an email to the concerned user.

        In:
            - node_id: the ID of the node where cloning was detected
        '''

        #---Init
        timestamp = datetime.utcnow()

        #---First, send notification to authorities
        authorities_messenger = Discorder.create()
        msg_authorities = '# Cloning detected!\n'
        msg_authorities += f'UTC time: `{timestamp}`\n'
        msg_authorities += f'Parking (node id): `{node_id}`\n'
        msg_authorities += f'User (UID): `{self._uid}`'

        success = authorities_messenger.send(msg_authorities)

        if not success:
            print('===================================')
            print('Notification to authorities failed!')
            print(f'Timestamp: {timestamp}')
            print('===================================')
            print('The message:')
            print(msg_authorities)
            print('===================================')

        #---Then email the concerned user
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        user_email_addr = self._user['profile']['email']
        user_username = self._user['profile']['username']

        msg_user = f'Hello {user_username},\n\n'
        msg_user += f'Suspicious activity has been detected at {timestamp} with your badge ID (badge cloning).\n'
        msg_user += 'Your account has been suspended.\n'
        msg_user += 'For more details and if you are not at the origin of this, please contact the parking service.\n\n'
        msg_user += 'This is an automated email. Please do not reply to it; your message would not be read.\n'
        msg_user += 'This email has been sent to you because you have an account on the parking service.'

        emailer = Emailer.create()
        emailer.send(user_email_addr, 'Parking service - account suspended after suspicious activity', msg_user)

##-Account management
class AccountManagement:
    '''Class handling the account management'''

    def __init__(self, uid: str, frontend_url: str, db_service: DatabaseService):
        '''
        Initiates the class.

        In:
            - uid: the user's UID (for the account).
            - frontend_url: the base URL of the frontend server
            - db_service: the DB controller
        '''

        self._uid = uid
        self._frontend_url = frontend_url
        self._db_service = db_service

        self._user_checker = UserCheck(db_service, uid)

    def create(self, data: dict[str, Any]) -> str:
        '''
        Creates a new user account from the given data.

        In:
            - data: the data to initiate the account values.
            Of the shape (note that "_id" is not provided here, because it is `self._uid`):
            {
                "profile": {
                    "username": str,
                    "email": str,
                    "is_admin": bool
                }
            }

        Out:
            str: the activation code

        Raises:
            ValueError if `data` is malformed
        '''

        # Validate input format
        if 'profile' not in data:
            raise ValueError('Field "profile" is missing from `data`')

        for field in {'username', 'email', 'is_admin'}:
            if field not in data['profile']:
                raise ValueError(f'Field "{field}" is missing from `data["profile"]`')

        # Add id to data
        data['_id'] = self._uid

        # Ensure uniqueness of username
        if self._db_service.query_drs('user', {'username': data['profile']['username']}) != []:
            raise ValueError('Field "username" is already used by an other user.')

        # Create user with factory
        dr_factory = DRFactory('src/virtualization/templates/user.yaml')
        user = dr_factory.create_dr('user', data)

        user_id = self._db_service.save_dr('user', user)
        assert user_id == self._uid

        # Send email to user with the code to activate the account
        pwd_reset_tk = self.send_pwd_reset(creation=True)

        return pwd_reset_tk

    def send_pwd_reset(self, creation: bool) -> str:
        '''
        Sends an email to the user with the information needed to reset password / activate account.

        It also generates the code (and write it into the DB).

        In:
            - creation: True for account creation, False for password reset

        Out:
            str: the activation code
        '''

        # Set a random token for password reset
        pwd_reset_tk = ''.join(secrets.choice('0123456789') for _ in range(10))
        self._user_checker.update_content({'pwd_reset_tk': pwd_reset_tk})

        # Send email
        emailer = Emailer.create()
        email_addr = self._user_checker.get()['profile']['email']

        if creation:
            subject = 'Parking Service - Account created'
            body = self._get_email_body_for_account_creation()
        else:
            subject = f'Parking Service - Password reset - code: {pwd_reset_tk}'
            body = self._get_email_body_for_pwd_reset()

        emailer.send(email_addr, subject, body)

        return pwd_reset_tk

    def _get_email_body_for_account_creation(self) -> str:
        '''Creates the email body to send for account creation'''

        user = self._user_checker.get()

        url = self._frontend_url + '/pwd_reset'
        username = user['profile']['username']
        pwd_reset_tk = user['pwd_reset_tk']

        body = f'Hello {username},\n\n'
        body += 'Your account on the Parking Service has been created!\n'
        body += 'To activate your account, please follow this link:\n'
        body += f'{url}\n'
        body += f'Your one-time code is: {pwd_reset_tk}\n'
        body += f'Your username is: {username}.\n\n'
        body += 'Have a nice day and see you soon in our parkings,\n'
        body += 'The parking team\n\n'
        body += 'This is an automated email. Do not reply.'

        return body

    def _get_email_body_for_pwd_reset(self) -> str:
        '''Creates the email body to send for password reset'''

        user = self._user_checker.get()

        url = self._frontend_url + '/pwd_reset'
        username = user['profile']['username']
        pwd_reset_tk = user['pwd_reset_tk']

        body = f'Hello {username},\n\n'
        body += 'Someone (hopefully you) has started a password reset procedure. If you did not initiated the action, you can safely ignore this email (but you might want to change your password).\n'
        body += 'To change your password, please follow this link:\n'
        body += f'{url}\n'
        body += f'And your one-time code is: {pwd_reset_tk}\n\n'
        body += 'Have a nice day and see you soon in our parkings,\n'
        body += 'The parking team\n\n'
        body += 'This is an automated email. Do not reply.'

        return body

