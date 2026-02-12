#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Handles nodes updates'''

##-Imports
from src.application.mqtt_handler import NodeMQTTHandler
from src.application.notification_handlers import Discorder, Emailer
from src.application.user_management import UserCheck
from src.services.database_service import DatabaseService

from datetime import datetime

##-Node management
class NodeManagement:
    '''Class handling node management (status update, reservation, ...)'''

    def __init__(self, node_id: str, db_service: DatabaseService, mqtt_handler: NodeMQTTHandler):
        '''
        Initiates the class

        In:
            - node_id: the ID of the node
            - db_service: the DB controller
            - mqtt_handler: the MQTT handler
        '''

        self._node_id = node_id
        self._db_service = db_service
        self._mqtt_handler = mqtt_handler

        self._node: dict[str, str] | None = None # Will be set by self.is_id_valid in order to minimise calls to the DB

    def is_id_valid(self) -> bool:
        '''
        Checks if the node ID is present in the database

        Out:
            True   if the node's UID is present in the DB
            False  otherwise
        '''
    
        self._node = self._db_service.get_dr('node', self._node_id)
        return self._node is not None

    def update_content(self, update_data: dict):
        '''
        Updates the data of the node in the database.
        Does not do any check.

        In:
            - update_data: the data to update, shaped as in the database.
        '''

        # Always update the 'updated at' time stamp
        update_data['metadata'] = {'updated_at': datetime.utcnow()}
    
        self._db_service.update_dr('node', self._node_id, update_data)

    def get_status(self) -> str:
        '''Retrieves the current status of the node from the database.'''
    
        # Check if node exists
        if not self.is_id_valid():
            raise ValueError('Node ID not found')

        return self._node['data']['status']

    def new_status_from_node(self, new_status: str):
        '''
        Handle actions to perform when the node wants to change status to `status`.

        Possible changes:
            free | reserved -> occupied:   valid parking. Change `user.is_parked` and `node.used_by` (already done earlier by POST /api/nodes/<node_id>)
            free | reserved -> violation:  node timeout (no badge scanned). Call authority notification
            violation -> free | reserved:  nothing to do here
            reserved -> free:              node timeout (no car came). So email the user + change `node.used_by`
            occupied -> free:              car left. Change `node.used_by`, `user.is_parked`

        Note: the states `waiting_for_authentication` and `unauthorized` are not used in the platform.
        Note 2: the status itself is updated in the DB by the caller directly.

        In:
            - new_status: the new status of the node
        Out:
            None        if everything worked fine
            ValueError  if node not found or impossible transition detected
        '''

        if not self.is_id_valid():
            raise ValueError('node ID not found')

        if new_status in ('waiting_for_authentication', 'unauthorized'):
            return # Ignore these statuses

        # Init
        old_status = self._node['data']['status']

        # Logic
        if old_status in ('free', 'reserved') and new_status == 'occupied':
            pass # Already done by the POST on /api/nodes/<node_id> (to check user authentication)

        elif old_status in ('free', 'reserved') and new_status == 'violation':
            self._send_violation_event()
        
        elif old_status == 'violation' and new_status in ('free', 'reserved'):
            pass # Nothing to do here

        elif old_status == 'reserved' and new_status == 'free': # Reservation timeout
            uid = self._node['used_by']

            UserCheck(self._db_service, uid).decrease_nb_reservations()
            self.update_content({'used_by': ''})

            self._send_reservation_timeout_event(uid)

        elif old_status == 'occupied' and new_status == 'free': # Car left
            uid = self._node['used_by']
            self._db_service.update_dr('user', uid, {'is_parked': False})
            self.update_content({'used_by': ''})

        else:
            raise ValueError(f'Impossible situation: node cannot switch from {old_status} to {new_status}')

    def reserve(self, uid: str) -> bool:
        '''
        Called when user `uid` wants to reserve `self._node_id`.
        I.e when the user PATCHes `{status: "reserved"}` on `self._node_id`.

        Note: the status itself is updated (to `reserved`) in the DB by the caller directly.

        In:
            - uid: the UID of the user trying to reserve the node
        Out:
            True   if the node gets successfully reserved
            False  otherwise
        '''

        # Check if user is allowed to reserve
        user_check = UserCheck(self._db_service, uid)

        if not user_check.is_uid_valid():
            return False
        if not user_check.is_authorized():
            return False
        if not user_check.can_reserve():
            return False

        # Check if node is still free
        if self._node['data']['status'] != 'free':
            return False

        # Take reservation
        user_check.increase_nb_reservations()
        self.update_content({'used_by': uid})

        # Send reservation to the node (MQTT)
        self._mqtt_handler.reserve_node(self._node_id)

        return True
    
    def cancel_reservation(self, uid: str):
        '''
        Called when user `uid` wants to cancel its reservation for the node `self._node_id`.

        Note: it is the caller that will 

        In:
            - uid: the user's UID
        Out:
            True   if the cancellation is successful
            False  otherwise
        '''

        # Check user
        user_check = UserCheck(self._db_service, uid)

        if not user_check.is_uid_valid():
            return False

        # Check that reservation exists
        if self.get_status() != 'reserved':
            return False

        if self._node['used_by'] != uid:
            return False

        # Cancel reservation
        user_check.decrease_nb_reservations()
        self.update_content({'used_by': ''})

        # Send cancellation to the node (MQTT)
        self._mqtt_handler.cancel_reservation(self._node_id)

        return True

    def _send_violation_event(self):
        '''
        Called when someone parks and do not scan the badge.

        Sends notification to authorities.
        '''

        #---Init
        timestamp = datetime.utcnow()

        #---First, send notification to authorities
        authorities_messenger = Discorder.create()
        msg_authorities = '# Illegal parking detected!\n'
        msg_authorities += f'UTC time: `{timestamp}`\n'
        msg_authorities += f'Parking (node id): `{self._node_id}`, location: `{self._node["profile"]["position"]}`\n\n'
        msg_authorities += 'Details: someone parked on this parking spot but did not validate its badge (if he has one)'

        success = authorities_messenger.send(msg_authorities)

        if not success:
            print('===================================')
            print('Notification to authorities failed!')
            print(f'Timestamp: {timestamp}')
            print('===================================')
            print('The message:')
            print(msg_authorities)
            print('===================================')

    def _send_reservation_timeout_event(self, uid: str):
        '''
        Called when reserved parking spot times out (-> free)

        Sends an email to the concerned user.
        '''

        # Check if user exists
        user = self._db_service.get_dr('user', uid)
        if user is None:
            raise ValueError('User not found')

        user_email_addr = user['profile']['email']
        user_username = user['profile']['username']

        msg_user = f'Hello {user_username},\n\n'
        msg_user += f'You reserved a parking spot (location: {self._node["profile"]["position"]}) earlier today.\n'
        msg_user += 'As you did not come to park one hour after the reservation was made, the parking is not reserved anymore.\n\n'
        msg_user += 'Thank you for your understanding.\n\n'
        msg_user += 'This is an automated email. Please do not reply to it; your message would not be read.\n'
        msg_user += 'This email has been sent to you because you have an account on the parking service.'

        emailer = Emailer.create()
        emailer.send(user_email_addr, 'Parking service - reservation timed out', msg_user)
