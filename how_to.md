## Set Up the Environment
### First time Docker lunch
```
docker-compose up --build
```
### Restart the Docker
```
docker-compose down
docker-compose up --build
```
### Open terminal in VS code
```
toggle terminal
```
### Check port
```
lsof -i :5000
```
```
kill -9 <PID>
```

Communicatetion between 2 Services/APIs (Python and Node.js):
```
curl -X POST http://localhost:5000/events/create -H "Content-Type: application/json" -d '{"title": "Meeting", "description": "Team sync", "date": "2024-10-26"}'

```
## Check+Confirm if all services are running

```
docker ps
```

## Status Endpoint (Simple Endpoint for All Services)

Each service (Event Service, User Service, Gateway, and Service Discovery) has a /status endpoint to check if they are running.

Testing:
For Event Service, run:
```
curl http://localhost:50051/status
```
For User Service, run:
```
curl http://localhost:50052/status
```
For Gateway, run:
```
curl http://localhost:5000/status
```
For Service Discovery, run:
```
curl http://localhost:8000/status
```

Each should return a response confirming that the service is running (e.g., `Service is running`).
