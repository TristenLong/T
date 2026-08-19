import requests
import json

BASE_URL = 'http://localhost:5000'

def test_vitals():
    try:
        r = requests.get(f'{BASE_URL}/api/pulse', timeout=5)
        print(f'VITALS: {r.json()}')
    except Exception as e:
        print(f'LOGIC_CORE_OFFLINE: {e}')

def test_history():
    try:
        r = requests.get(f'{BASE_URL}/api/history', timeout=5)
        print(f'HISTORY: {len(r.json())} items found')
    except Exception as e:
        print(f'HISTORY_FETCH_FAILED: {e}')

if __name__ == '__main__':
    print('--- JESTER V081 SMOKE TEST ---')
    test_vitals()
    test_history()
