#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Define handlers to deliver notifications (email, discord)'''

##-Imports
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

import requests

from dotenv import load_dotenv
import os

##-Util
def load_env_vars():
    '''Load environment variables'''

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

##-Email
class Emailer:
    '''Defines an object that sends emails'''

    def __init__(self, sender_addr: str, sender_pwd: str, smtp_url: str, smtp_port: int = 465):
        '''
        Initiates the object

        In:
            - sender_addr: the email address of the sender
            - sender_pwd: the password of the sender
            - smtp_url: the url of the smtp server (e.g mail.example.com)
            - smtp_port: the port used by the smtp server
        '''

        self._sender_addr = sender_addr
        self._sender_pwd = sender_pwd
        self._smtp_url = smtp_url
        self._smtp_port = smtp_port

        self.server = None

    def _connect(self):
        '''
        Tries to connect and login to the smtp server.

        Out:
            None
            ConnectionError  If an error occured
        '''
    
        try:
            self.server = smtplib.SMTP_SSL(self._smtp_url, self._smtp_port)
            self.server.login(self._sender_addr, self._sender_pwd)

        except Exception as e:
            raise ConnectionError(f'Emailer._connect: error while trying to connect to smtp server: "{e}"')

    def _disconnect(self):
        '''Closes the connection to the smtp server (if it exists).'''

        if self.server is not None:
            self.server.close()
            self.server = None

    def _connect_and_send(self, recipient: str, text: str):
        '''
        Connects and login to the server, sends the message `text`, and closes the connection.

        In:
            - recipient: the recipient's email address
            - text: the email text to send (contains 'From', 'To', 'Subject' and 'body')
        '''
    
        self._connect()

        try:
            self.server.sendmail(self._sender_addr, recipient, text)

        except Exception as e:
            raise Exception('Emailer._connect_and_send: error while sending email')

        finally:
            self._disconnect()

    def send(self, recipient: str, subject: str, body: str):
        '''
        Sends and email to `recipient`.

        In:
            - recipient: the email address of the recipient
            - subject: the subject of the email to send
            - body: the body of the email to send
        '''
    
        # Create message
        message = MIMEMultipart()

        message['From'] = self._sender_addr
        message['To'] = recipient
        message['Subject'] = subject

        # Critical additional headers
        message['Date'] = formatdate(localtime=True)
        # message['Message-ID'] = f"<{uuid.uuid4()}@example.com>"
        
        # Add standard headers to improve deliverability
        message.add_header('X-Mailer', 'Python')
        message.add_header('Precedence', 'bulk')
        message.add_header('Auto-Submitted', 'auto-generated')

        # Attach body
        message.attach(MIMEText(body, 'plain'))

        text = message.as_string()

        self._connect_and_send(recipient, text)

    def __repr__(self) -> str:
        '''stringify settings'''

        return f'Emailer({self._sender_addr}, {"*"*len(self._sender_pwd)}, {self._smtp_url}, {self._smtp_port})'

    @staticmethod
    def create() -> Emailer:
        '''Creates an instance of this class by reading environment variables (and .env file).'''

        # Load .env file
        load_env_vars()

        # Get env vars
        sender_addr = os.environ.get('MX_SENDER_ADDR')
        sender_pwd = os.environ.get('MX_SENDER_PWD')
        smtp_url = os.environ.get('MX_SMTP_URL')
        smtp_port = os.environ.get('MX_SMTP_PORT')

        emailer = Emailer(sender_addr, sender_pwd, smtp_url, smtp_port)

        return emailer

##-Discord
class Discorder:
    '''Defines an object that sends discord messages'''

    def __init__(self, webhook_url: str):
        '''
        Initiates the object

        In:
            - webhook_url: the webhook url
        '''

        self._webhook_url = webhook_url

    def send(self, msg: str, username: str = 'IoT_platform') -> bool:
        '''
        Sends `msg` to discord

        In:
            - msg: the message to send
            - username: the bot username
        Out:
            True   if message successfully delivered
            False  otherwise
        '''
    
        data = {
            'username': username,
            'content': msg
        }

        response = requests.post(self._webhook_url, json=data)

        return response.status_code == 204

    @staticmethod
    def create() -> Discorder:
        '''Creates an instance of this class by reading environment variables (and .env file).'''
    
        # Load .env file
        load_env_vars()

        # Create discorder
        webhook_url = os.environ.get('DISCORD_WEBHOOK')
        discorder = Discorder(webhook_url)

        return discorder


##-Test
if __name__ == '__main__':
    print('Testing email')

    emailer = Emailer.create()
    print(emailer)

    print('send test email...')
    emailer.send('test@lasercata.com', 'test from python', 'Test from python!')

    print('Testing discord')

    discorder = Discorder.create()
    discorder.send('Test message from python!')

