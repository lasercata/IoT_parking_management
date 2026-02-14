#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##-Imports
#---External
from flask import Flask
from flask_cors import CORS

from sys import argv

from dotenv import load_dotenv
import os

#---Internal
from src.virtualization.digital_replica.schema_registry import SchemaRegistry
from src.services.database_service import DatabaseService
from src.digital_twin.dt_factory import DTFactory

from src.application.api import register_api_blueprints
from src.application.nodes_api import register_node_blueprint
from src.application.users_api import register_user_blueprint
from src.application.mqtt_handler import NodeMQTTHandler

from config.config_loader import ConfigLoader

##-Init
# Construct the path to the .env file in the parent directory
dotenv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    '.env'
)

# Load the .env file from the parent directory
load_dotenv(dotenv_path)


##-Main
class FlaskServer:
    def __init__(self):
        self.app = Flask(__name__)

        # Secret key for JWT
        # IMPORTANT: use the same secret key as in the backend
        self.app.config['SECRET_KEY'] = os.environ.get('JWT_SHARED_TOKEN')

        CORS(self.app) #TODO: edit this for production

        self._init_components()
        self._register_blueprints()

    def _init_components(self):
        """Initialize all required components and store them in app config"""

        schema_registry = SchemaRegistry()
        schema_registry.load_schema('node', 'src/virtualization/templates/node.yaml')
        schema_registry.load_schema('user', 'src/virtualization/templates/user.yaml')

        # Load database configuration
        # db_config = ConfigLoader.load_database_config()
        db_config = ConfigLoader.load_database_config_env()
        connection_string = ConfigLoader.build_connection_string(db_config)

        # Initialize DatabaseService with populated schema_registry
        db_service = DatabaseService(
            connection_string=connection_string,
            db_name=db_config["settings"]["name"],
            schema_registry=schema_registry,
        )
        db_service.connect()

        # Initialize DTFactory
        dt_factory = DTFactory(db_service, schema_registry)

        # Initialize MQTT handler
        self.app.config['MQTT_CONFIG'] = {
            'broker': os.environ.get('MQTT_DOMAIN'),
            'port': os.environ.get('MQTT_PORT'),
            'username': os.environ.get('MQTT_USERNAME'),
            'password': os.environ.get('MQTT_PWD')
        }
        mqtt_handler = NodeMQTTHandler(self.app)

        # Store references
        self.app.config['SCHEMA_REGISTRY'] = schema_registry
        self.app.config['DB_SERVICE'] = db_service
        self.app.config['DT_FACTORY'] = dt_factory
        self.app.config['MQTT_HANDLER'] = mqtt_handler

        self.app.config['FRONTEND_URL'] = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

    def _register_blueprints(self):
        """Register all API blueprints"""

        register_api_blueprints(self.app)
        register_node_blueprint(self.app)
        register_user_blueprint(self.app)

    def run(self, host="0.0.0.0", port=5000, debug=True):
        """Run the Flask server"""

        try:
            self.app.config['MQTT_HANDLER'].start()
            self.app.run(host=host, port=port, debug=debug)

        finally:
            # Cleanup on server shutdown
            if "DB_SERVICE" in self.app.config:
                self.app.config["DB_SERVICE"].disconnect()

            self.app.config['MQTT_HANDLER'].stop()

server = FlaskServer()
app = server.app # Needed to run with gunicorn

if __name__ == "__main__":
    if len(argv) > 1:
        port = int(argv[1])
    else:
        port = 5000

    server.run(port=port)
