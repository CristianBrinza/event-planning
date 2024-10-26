import grpc
from concurrent import futures
import threading
import time
from flask import Flask, request, jsonify
import event_pb2
import event_pb2_grpc
import user_pb2
import user_pb2_grpc

MAX_CONCURRENT_TASKS = 10
TASK_TIMEOUT = 5
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_TIME_WINDOW = TASK_TIMEOUT * 3.5

class CircuitBreaker:
    def __init__(self, threshold, time_window):
        self.threshold = threshold
        self.time_window = time_window
        self.failures = []
        self.lock = threading.Lock()
        self.open = False

    def call(self, func, *args, **kwargs):
        with self.lock:
            if self.open:
                raise Exception("Circuit breaker is open")
            try:
                result = func(*args, **kwargs)
                self.failures = []
                return result
            except Exception as e:
                self.failures.append(time.time())
                self.failures = [f for f in self.failures if f > time.time() - self.time_window]
                if len(self.failures) >= self.threshold:
                    self.open = True
                    print("Circuit breaker tripped, service removed")
                raise e

app = Flask(__name__)

event_service_addresses = ['event_service:50051', 'event_service:50052', 'event_service:50053']
user_service_addresses = ['user_service:50052', 'user_service:50053', 'user_service:50054']

event_stubs = []
user_stubs = []
event_loads = []
user_loads = []

for addr in event_service_addresses:
    channel = grpc.insecure_channel(addr)
    stub = event_pb2_grpc.EventServiceStub(channel)
    event_stubs.append(stub)
    event_loads.append(0)

for addr in user_service_addresses:
    channel = grpc.insecure_channel(addr)
    stub = user_pb2_grpc.UserServiceStub(channel)
    user_stubs.append(stub)
    user_loads.append(0)

event_circuit_breakers = [CircuitBreaker(CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIME_WINDOW) for _ in event_stubs]
user_circuit_breakers = [CircuitBreaker(CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIME_WINDOW) for _ in user_stubs]

def get_event_stub():
    min_load = min(event_loads)
    index = event_loads.index(min_load)
    event_loads[index] += 1
    return event_stubs[index], index

def release_event_stub(index):
    event_loads[index] -= 1

@app.route('/status', methods=['GET'])
def status():
    return 'Gateway is running', 200

@app.route('/events/create', methods=['POST'])
def create_event():
    stub, index = get_event_stub()
    try:
        request_data = request.get_json()
        event_request = event_pb2.CreateEventRequest(
            title=request_data['title'],
            description=request_data['description'],
            date=request_data['date']
        )
        response = event_circuit_breakers[index].call(
            stub.CreateEvent,
            event_request,
            timeout=TASK_TIMEOUT
        )
        return jsonify({'id': response.id}), 200
    except Exception as e:
        return str(e), 500
    finally:
        release_event_stub(index)

def main():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
