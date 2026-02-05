#!/usr/bin/env bash

# Create a directory for certificates
cd mosquitto/certs

# Generate CA key and certificate
openssl req -new -x509 -days 365 -extensions v3_ca -keyout ca.key -out ca.crt

# Generate server key
openssl genrsa -out server.key 2048

# Create a certificate signing request
openssl req -new -key server.key -out server.csr

# Self-sign the server certificate
openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt

chown 3333:3333 *
