# CyberSecurity-Project

Secure encrypted chat application built with Python using WebSockets, AES encryption, and Ed25519 digital signatures.

## Features

* End-to-end encrypted messaging
* Digital signature verification
* Secure client-server communication
* User authentication system
* Modern GUI built with Tkinter
* Real-time active users dashboard
* Identity verification for connected peers
* Security event logging
* Multi-user chat support

## Technologies Used

* Python
* WebSockets
* Tkinter
* Cryptography Library
* AES-GCM Encryption
* Ed25519 Digital Signatures
* AsyncIO

## Project Structure

```bash
secure_chat_server.py   # Server application
secure_chat_client.py   # Client application
```

## Installation

Install the required libraries:

```bash
pip install websockets cryptography
```

## How to Run

### Start the Server

```bash
python secure_chat_server.py
```

### Start the Client

```bash
python secure_chat_client.py
```

## Default Configuration

* Server Port: `5000`
* Default Password: `123`

## Security Features

* AES-GCM encryption for message confidentiality
* Ed25519 signatures for message authenticity
* Identity key management
* Peer verification system
* Protection against tampered messages

## Screenshots

(Add screenshots here)

## Future Improvements

* File sharing support
* Private chat rooms
* Voice communication
* Database integration
* Stronger authentication system

## Author

Mohamed Adel
ahmed ehab 
basel ashraf
