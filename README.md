# IoT parking management project

## Code structure
```
IoT_parking_management/
├── analysis_document/  report
├── frontend/           Frontend code
├── platform/           Backend (IoT platform) code
├── node/               Hardware code (parking nodes)
│
├── docker-compose.yaml
└── README.md
```

## Setup and run
### Env
Create `.env`:
```
cp .env.example .env
```

Then edit it (set empty variables).

### Mosquitto
Run:
```
cd data/
sudo ./create_mosquitto.sh
```

And run only this for development (use let's encrypt for production):
```
sudo ./create_self_signed_certs.sh
```

### Run (production)
```
docker compose up -d
```

### Run (development)
- DB and broker in docker:
```
docker compose up iot-mongodb iot-mosquitto -d
```

- Platform:
```
cd platform/
python app.py
```

- Frontend (in an other terminal):
```
cd frontend/
python app.py
```

Then go to [`localhost:3000`](http://localhost:3000/)
