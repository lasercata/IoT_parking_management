from flask import current_app
import paho.mqtt.client as mqtt
from datetime import datetime
import json
import logging
import time
from threading import Thread, Event

logger = logging.getLogger(__name__)


class NodeMQTTHandler:
    '''Handles the MQTT connection for the platform -> node communication'''

    def __init__(self, app):
        self.app = app
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._setup_mqtt()

        self.connected = False
        self.stopping = Event()
        self.reconnect_thread = None

    def _setup_mqtt(self):
        """Setup MQTT client with configuration from app"""

        config = self.app.config.get('MQTT_CONFIG', {})
        self.broker = config.get('broker', 'broker.mqttdashboard.com')
        self.port = config.get('port', 1883)

        # self.topic = "winery/+/+/temperature"  # floor/room/temperature

    def start(self):
        """Start MQTT client in non-blocking way"""

        try:
            # Start MQTT loop in background thread
            self.client.loop_start()

            # Try to connect
            self._connect()

            # Start reconnection thread
            self.reconnect_thread = Thread(target=self._reconnection_loop)
            self.reconnect_thread.daemon = True
            self.reconnect_thread.start()

            logger.info("MQTT handler started")

        except Exception as e:
            logger.error(f"Error starting MQTT handler: {e}")
            # Don't raise the exception - allow the application to continue

    def stop(self):
        """Stop MQTT client"""

        self.stopping.set()
        if self.reconnect_thread:
            self.reconnect_thread.join(timeout=1.0)

        self.client.loop_stop()
        if self.connected:
            self.client.disconnect()

        logger.info("MQTT handler stopped")

    def _connect(self):
        """Attempts to connect to the broker"""

        try:
            self.client.connect(self.broker, self.port, 60)
            logger.info(f"Attempting connection to {self.broker}:{self.port}")

        except Exception as e:
            logger.error(f"Connection attempt failed: {e}")
            self.connected = False

    def _reconnection_loop(self):
        """Background thread that handles reconnection"""

        while not self.stopping.is_set():
            if not self.connected:
                logger.info("Attempting to reconnect...")

                try:
                    self._connect()
                except Exception as e:
                    logger.error(f"Reconnection attempt failed: {e}")

            time.sleep(5)  # Wait 5 seconds between reconnection attempts

    def _on_connect(self, client, userdata, flags, rc):
        """Handle connection to broker"""

        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")

            # # Subscribe to temperature topics
            # client.subscribe(self.topic)
            # logger.info(f"Subscribed to {self.topic}")

        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection from broker"""

        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")

    def _on_message(self, client, userdata, msg):
        """Handle incoming messages (none should come)"""

        pass

    @property
    def is_connected(self):
        """Check if client is currently connected"""

        return self.connected
