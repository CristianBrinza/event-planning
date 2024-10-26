const grpc = require('grpc');
const protoLoader = require('@grpc/proto-loader');
const sqlite3 = require('sqlite3').verbose();
const LRU = require('lru-cache');
const path = require('path');
const PROTO_PATH = path.join(__dirname, 'protos', 'user.proto');

const packageDefinition = protoLoader.loadSync(
    PROTO_PATH,
    {
        keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true
    });
const userProto = grpc.loadPackageDefinition(packageDefinition).user;

const MAX_CONCURRENT_TASKS = 10;
const TASK_TIMEOUT = 5000;
const CRITICAL_LOAD = 60;

let requestCount = 0;
let startTime = Date.now();

const cache = new LRU({ max: 100 });

const db = new sqlite3.Database('users.db');
db.serialize(() => {
    db.run(`CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )`);
});

function monitorLoad() {
    setInterval(() => {
        let elapsed = (Date.now() - startTime) / 1000;
        if (elapsed > 0) {
            let load = requestCount / elapsed;
            if (load > CRITICAL_LOAD) {
                console.log('ALERT: High load detected on UserService');
            }
            requestCount = 0;
            startTime = Date.now();
        }
    }, 1000);
}

function SendNotification(call, callback) {
    requestCount++;
    console.log(`Notification to user ${call.request.user_id}: ${call.request.message}`);
    callback(null, { success: true });
}

function Status(call, callback) {
    callback(null, { status: 'UserService is running' });
}

function main() {
    const server = new grpc.Server();
    server.addService(userProto.UserService.service, {
        SendNotification: SendNotification,
        Status: Status
    });
    server.bind('0.0.0.0:50052', grpc.ServerCredentials.createInsecure());
    server.start();
    console.log('UserService started on port 50052');
    monitorLoad();
}

main();
