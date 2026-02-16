#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Loads the variables from the .env'''

##-Imports
import os
from dotenv import load_dotenv

from src.database import DatabaseService

##-Load
def bring_dotenv():
    '''Loads the .env file for "os.environ"'''

    # Define potential paths to check for .env files (because we are in platform/src/application/, so .env is at ../../../.env)
    potential_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),  # current directory
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),  # parent directory
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'),  # grandparent directory
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env')  # great-grandparent directory
    ]

    # Load the first existing .env file
    for path in potential_paths:
        if os.path.exists(path):
            load_dotenv(path)
            print(f'Loaded environment variables from: {path}')
            break

def get_vars() -> dict[str, str]:
    '''
    Gets needed variables from environment

    Out:
        The following dictionary:
        {
            "PLATFORM_URL": str,
            "SECRET_KEY": str,
        }
    '''

    bring_dotenv()

    ret = {}

    ret['PLATFORM_URL'] = os.environ.get('PLATFORM_URL', default='http://localhost:5000')

    # Secret key for JWT (IMPORTANT: use the same secret key as in the backend)
    ret['SECRET_KEY'] = os.environ.get('JWT_SHARED_TOKEN')

    if ret['SECRET_KEY'] is None:
        raise ValueError('Please fill the .env correctly (SECRET_KEY)')
    
    return ret

def get_db_config() -> dict[str, str]:
    '''
    Retrieve MongoDB connection details from environment variables

    Out:
        The following dict:
        {
            "username": str,
            "password": str,
            "database": str,
            "port": 27017,
            "uri": str
        }
    '''

    ret = {}
    ret['username'] = os.environ.get('MONGO_USERNAME')
    ret['password'] = os.environ.get('MONGO_PASSWORD')
    ret['database'] = os.environ.get('MONGO_DATABASE')
    ret['ip'] = os.environ.get('MONGO_IP', 'localhost')
    ret['port'] = int(os.environ.get('MONGO_PORT', 27017))

    # ret['uri'] = os.environ.get('MONGODB_URI', f'mongodb://{ret["username"]}:{ret["password"]}@localhost:27017/{ret["database"]}')
    ret['uri'] = os.environ.get('MONGODB_URI', f'mongodb://{ret["username"]}:{ret["password"]}@{ret["ip"]}:{ret["port"]}')

    return ret

def get_db_service() -> DatabaseService:
    '''Reads the env vars, creates the database controller, and attempts to connect it'''

    db_config = get_db_config()

    db_service = DatabaseService(db_config['uri'], db_config['database'])
    db_service.connect()

    return db_service
