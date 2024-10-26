from flask import Flask, request, jsonify

app = Flask(__name__)

services = {}

@app.route('/register', methods=['GET'])
def register_service():
    name = request.args.get('name')
    address = request.args.get('address')
    if not name or not address:
        return 'Missing name or address', 400
    if name not in services:
        services[name] = []
    services[name].append(address)
    return 'Registered', 200

@app.route('/get', methods=['GET'])
def get_service():
    name = request.args.get('name')
    if not name:
        return 'Missing name', 400
    if name not in services:
        return 'Service not found', 404
    return jsonify(services[name]), 200

@app.route('/status', methods=['GET'])
def status():
    return 'Service Discovery is running', 200

def main():
    app.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    main()
