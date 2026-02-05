import yaml
from typing import Dict
from dotenv import load_dotenv
import os

##-Init
# Construct the path to the .env file in the parent directory
dotenv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    '.env'
)

# Load the .env file from the parent directory
load_dotenv(dotenv_path)


class ConfigLoader:
    @staticmethod
    def load_database_config(config_path: str = "config/database.yaml") -> Dict:
        """Load database configuration from YAML file"""

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if not config or "database" not in config:
            raise ValueError("Invalid configuration file: missing database section")

        return config["database"]

    @staticmethod
    def load_database_config_env(config_path: str = "config/database.yaml") -> Dict:
        """Load database configuration from environment (here from ../.env)"""

        # Retrieve MongoDB connection details from environment variables
        mongo_username = os.environ.get('MONGO_USERNAME')
        mongo_password = os.environ.get('MONGO_PASSWORD')
        mongo_database = os.environ.get('MONGO_DATABASE')
        mongodb_uri = os.environ.get('MONGODB_URI', f'mongodb://{mongo_username}:{mongo_password}@localhost:27017/{mongo_database}')

        ret = {
            'connection': {
                'host': mongodb_uri.split('@')[1].split(':')[0],
                'port': 27017,
                'username': mongo_username,
                'password': mongo_password
            },
            'settings': {
                'name': mongo_database,
                'auth_source': 'admin'
            }
        }

        return ret

    @staticmethod
    def build_connection_string(config: Dict) -> str:
        """Build MongoDB connection string from configuration"""

        conn = config["connection"]
        host = conn["host"]
        port = conn["port"]

        # Build authentication part if credentials are provided
        auth = ""
        if conn.get("username") and conn.get("password"):
            auth = f"{conn['username']}:{conn['password']}@"

        return f"mongodb://{auth}{host}:{port}"
