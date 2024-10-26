import grpc
from concurrent import futures
import threading
import time
import sqlite3
import event_pb2
import event_pb2_grpc
import user_pb2
import user_pb2_grpc
from cache import LRUCache

MAX_CONCURRENT_TASKS = 10
TASK_TIMEOUT = 5
CRITICAL_LOAD = 60
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

class EventService(event_pb2_grpc.EventServiceServicer):
    def __init__(self):
        self.db_lock = threading.Lock()
        self.conn = sqlite3.connect('events.db', check_same_thread=False)
        self.create_table()
        self.concurrent_limit = threading.Semaphore(MAX_CONCURRENT_TASKS)
        self.cache = LRUCache(100)
        self.request_count = 0
        self.start_time = time.time()
        self.circuit_breaker = CircuitBreaker(CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIME_WINDOW)
        self.user_stub = user_pb2_grpc.UserServiceStub(grpc.insecure_channel('user_service:50052'))

    def create_table(self):
        with self.db_lock:
            cursor = self.conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS events
                              (id INTEGER PRIMARY KEY AUTOINCREMENT,
                               title TEXT, description TEXT, date TEXT)''')
            self.conn.commit()

    def monitor_load(self):
        while True:
            time.sleep(1)
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                load = self.request_count / elapsed
                if load > CRITICAL_LOAD:
                    print("ALERT: High load detected on EventService")
                self.request_count = 0
                self.start_time = time.time()

    def CreateEvent(self, request, context):
        with self.concurrent_limit:
            self.request_count += 1
            try:
                with self.db_lock:
                    cursor = self.conn.cursor()
                    cursor.execute('INSERT INTO events (title, description, date) VALUES (?, ?, ?)',
                                   (request.title, request.description, request.date))
                    self.conn.commit()
                    event_id = cursor.lastrowid
                notification_request = user_pb2.NotificationRequest(
                    user_id='1',
                    message='Event Created: ' + request.title
                )
                try:
                    self.circuit_breaker.call(
                        self.user_stub.SendNotification,
                        notification_request,
                        timeout=TASK_TIMEOUT
                    )
                except Exception as e:
                    print("Failed to send notification:", e)
                return event_pb2.CreateEventResponse(id=str(event_id))
            except Exception as e:
                context.set_details(str(e))
                context.set_code(grpc.StatusCode.INTERNAL)
                return event_pb2.CreateEventResponse()

    def UpdateEvent(self, request, context):
        with self.concurrent_limit:
            self.request_count += 1
            try:
                with self.db_lock:
                    cursor = self.conn.cursor()
                    cursor.execute('UPDATE events SET title=?, description=?, date=? WHERE id=?',
                                   (request.title, request.description, request.date, request.id))
                    self.conn.commit()
                return event_pb2.UpdateEventResponse(success=True)
            except Exception as e:
                context.set_details(str(e))
                context.set_code(grpc.StatusCode.INTERNAL)
                return event_pb2.UpdateEventResponse(success=False)

    def ListEvents(self, request, context):
        with self.concurrent_limit:
            self.request_count += 1
            try:
                if 'events' in self.cache:
                    events = self.cache.get('events')
                else:
                    with self.db_lock:
                        cursor = self.conn.cursor()
                        cursor.execute('SELECT id, title, description, date FROM events')
                        events = [event_pb2.Event(id=str(row[0]), title=row[1], description=row[2], date=row[3])
                                  for row in cursor.fetchall()]
                        self.cache.put('events', events)
                return event_pb2.ListEventsResponse(events=events)
            except Exception as e:
                context.set_details(str(e))
                context.set_code(grpc.StatusCode.INTERNAL)
                return event_pb2.ListEventsResponse()

    def Status(self, request, context):
        return event_pb2.StatusResponse(status="EventService is running")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TASKS))
    event_pb2_grpc.add_EventServiceServicer_to_server(EventService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("EventService started on port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    threading.Thread(target=EventService().monitor_load).start()
    serve()
