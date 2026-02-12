#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Implements functions to manage user data'''

##-Imports
from src.application.notification_handlers import Discorder, Emailer
from src.services.database_service import DatabaseService
from datetime import datetime

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
        A user can have at most 1 reservation.

        Out:
            True        if the user has 0 reservation (he can reserve)
            False       otherwise
            ValueError  if UID not in DB
        '''
    
        # Check if user exists
        if not self.is_uid_valid():
            raise ValueError('User not found')

        return self._user['nb_reservations'] == 0

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

