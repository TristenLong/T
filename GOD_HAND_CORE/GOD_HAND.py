import os
import sys
import threading

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from loguru import logger

load_dotenv(override=True)

VERSION = 'V1000 UNIFIED'
PERSONA = 'JESTER V1000: THE GOD HAND'

app = Flask(__name__)
CORS(app)

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'ONLINE', 'version': VERSION, 'persona': PERSONA})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get('message', '')
    return jsonify({'response': f'THE GOD HAND acknowledges: {msg}', 'status': 'SYNCED'})

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify([])

@app.route('/api/pulse', methods=['GET'])
def pulse():
    import psutil
    return jsonify({
        'status': 'ONLINE',
        'cpu': psutil.cpu_percent(),
        'ram': psutil.virtual_memory().percent,
        'model': os.getenv('JESTER_PRIMARY_LLM', 'gemini-3.1-pro'),
        'logic_core': 'STABLE'
    })

@app.route('/api/matrix_status', methods=['GET'])
def matrix_status():
    return jsonify({'matrix_active': True, 'jester_version': VERSION})

def run_backend():
    logger.info(f'Starting {PERSONA} Backend on port 5000...')
    app.run(port=5000, host='0.0.0.0', debug=False, use_reloader=False)

def main():
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    logger.info(f'{PERSONA} UNIFIED SYSTEM ACTIVE.')
    os.system('python bot.py')

if __name__ == '__main__':
    main()
