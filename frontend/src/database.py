#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
from pymongo import MongoClient

##-Database service
class DatabaseService:
    '''Manages the connection and communication to the MongoDB database'''

    def __init__(self, connection_string: str, db_name: str):
        '''Initiates the class'''

        self.connection_string = connection_string
        self.db_name = db_name
        self.client = None
        self.db = None

        self.user_collection_name = 'user_collection'

    def connect(self) -> None:
        '''Tries to connect to the database'''

        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.db_name]

        except Exception as e:
            raise ConnectionError(f'Failed to connect to MongoDB: {e}')

    def disconnect(self) -> None:
        '''Disconnects from the database'''

        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def is_connected(self) -> bool:
        '''Checks if the connection to the database is active'''

        return self.client is not None and self.db is not None

    def get_user_by_id(self, user_id: str) -> dict | None:
        '''Retrieves a user from the DB by its ID'''

        return self._find_one({'_id': user_id})

    def get_user_by_username(self, username: str) -> dict | None:
        '''Retrieves a user from the DB by its username'''

        return self._find_one(
            {'profile.username': username}, # Find by username
            {'profile': 1, 'pwd_hash': 1, 'pwd_reset_tk': 1, 'violation_detected': 1} # Projection
        )

    def _find_one(self, *args, **kargs) -> dict | None:
        '''
        Calls `find_one` on the database.
        Do the checks (connected) and raise errors in case of failure.
        '''
    
        if not self.is_connected():
            raise ConnectionError('Not connected to MongoDB')

        try:
            return self.db[self.user_collection_name].find_one(*args, **kargs)

        except Exception as e:
            raise Exception(f'Failed to get user: {e}')

