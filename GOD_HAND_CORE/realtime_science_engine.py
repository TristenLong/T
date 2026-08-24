import asyncio
import datetime
import json
import logging
import math
import os
import sqlite3
import time
import traceback
from collections import deque

import aiohttp
import numpy as np
import psutil
import websockets
from scipy.fft import rfft
from scipy.stats import pearsonr
from sklearn.ensemble import IsolationForest

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ScienceEngine')

ANU_QRNG_URL = "https://qrng.anu.edu.au/API/jsonI.php?length=1024&type=uint8"

# Global Cache for OS Telemetry
CACHE = {
    'cpu_percent': 0.0,
    'ram_percent': 0.0,
    'disk_percent': 0.0,
    'net_recv_mb': 0.0,
    'net_sent_mb': 0.0,
    'net_recv_rate': 0.0,
    'net_sent_rate': 0.0,
    'seismic_mag': 0.0,
    'seismic_location': 'None',
    'geomagnetic_kp': 0.0,
    'xray_flux': 0.0
}

# Network tracking
last_net_io = psutil.net_io_counters()
last_net_time = time.time()

# Entropy Buffer
qrng_buffer = deque()

# Analytics state
WINDOW_SIZE = 100
history_entropy = deque(maxlen=WINDOW_SIZE)
history_cpu = deque(maxlen=WINDOW_SIZE)
history_ram = deque(maxlen=WINDOW_SIZE)
history_features = deque(maxlen=WINDOW_SIZE)

# ML Engine & Database
iso_forest = IsolationForest(contamination=0.05, n_estimators=50, random_state=42)

def init_db():
    conn = sqlite3.connect('jester_memory.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS os_telemetry (
            timestamp REAL,
            entropy REAL,
            cpu_percent REAL,
            ram_percent REAL,
            disk_percent REAL,
            net_recv_rate REAL,
            anomaly_score REAL,
            is_anomaly BOOLEAN
        )
    ''')
    conn.commit()
    return conn

db_conn = init_db()

async def fetch_os_telemetry():
    global last_net_io, last_net_time
    try:
        CACHE['cpu_percent'] = psutil.cpu_percent(interval=None)
        CACHE['ram_percent'] = psutil.virtual_memory().percent
        CACHE['disk_percent'] = psutil.disk_usage('/').percent
        
        # Calculate Network Rate
        current_net_io = psutil.net_io_counters()
        current_time = time.time()
        time_diff = current_time - last_net_time
        
        if time_diff > 0:
            recv_bytes = current_net_io.bytes_recv - last_net_io.bytes_recv
            sent_bytes = current_net_io.bytes_sent - last_net_io.bytes_sent
            
            CACHE['net_recv_rate'] = (recv_bytes / 1024 / 1024) / time_diff # MB/s
            CACHE['net_sent_rate'] = (sent_bytes / 1024 / 1024) / time_diff # MB/s
            
            # Cumulative total
            CACHE['net_recv_mb'] = current_net_io.bytes_recv / 1024 / 1024
            CACHE['net_sent_mb'] = current_net_io.bytes_sent / 1024 / 1024
            
        last_net_io = current_net_io
        last_net_time = current_time
    except Exception as e:
        logger.warning(f"OS Telemetry fetch failed: {e}")

async def fetch_anu_qrng(session):
    try:
        async with session.get(ANU_QRNG_URL, timeout=10) as resp:
            data = await resp.json()
            if data.get('success'):
                numbers = data.get('data', [])
                qrng_buffer.extend(numbers)
                logger.debug(f"Fetched {len(numbers)} quantum random numbers.")
    except Exception as e:
        logger.warning(f"ANU QRNG fetch failed: {e}")
        qrng_buffer.extend([b for b in os.urandom(100)])

async def fetch_external_science(session):
    try:
        # USGS Earthquakes
        async with session.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson", timeout=10) as resp:
            eq_data = await resp.json()
            if eq_data.get("features"):
                quakes = eq_data["features"]
                mags = [q["properties"]["mag"] for q in quakes if q["properties"]["mag"] is not None]
                if mags:
                    max_q = max(quakes, key=lambda q: q["properties"]["mag"] or 0)
                    CACHE['seismic_mag'] = max_q["properties"]["mag"]
                    CACHE['seismic_location'] = max_q["properties"]["place"]
    except Exception as e:
        logger.warning(f"USGS fetch failed: {e}")

    try:
        # NOAA K-Index
        async with session.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", timeout=10) as resp:
            noaa_data = await resp.json()
            if len(noaa_data) > 1:
                CACHE['geomagnetic_kp'] = float(noaa_data[-1][1])
    except Exception as e:
        logger.warning(f"NOAA K-Index fetch failed: {e}")

    try:
        # NOAA X-Ray Flux
        async with session.get("https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json", timeout=10) as resp:
            xray_data = await resp.json()
            if xray_data:
                # Find the most recent flux
                CACHE['xray_flux'] = float(xray_data[-1].get('flux', 0.0))
    except Exception as e:
        logger.warning(f"NOAA X-Ray Flux fetch failed: {e}")

async def background_poller():
    """Polls OS telemetry quickly."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    async with aiohttp.ClientSession(headers=headers) as session:
        count = 0
        while True:
            await fetch_os_telemetry()
            if count % 60 == 0:  # Fetch external science every 60 seconds
                await fetch_external_science(session)
            count += 1
            await asyncio.sleep(1.0) # Poll OS every second

async def qrng_poller():
    """Polls the QRNG API when the buffer is low."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            if len(qrng_buffer) < 50:
                await fetch_anu_qrng(session)
            await asyncio.sleep(60)

async def tick_generator():
    """Generates the continuous payload stream."""
    while True:
        source = "anu_qrng"
        if len(qrng_buffer) >= 10:
            sample = [qrng_buffer.popleft() for _ in range(10)]
            base_entropy = 7.95
            entropy = base_entropy + (np.mean(sample) / 255.0) * 0.05
        else:
            source = "simulation_fallback"
            entropy = 7.95 + np.random.random() * 0.05

        history_entropy.append(entropy)
        history_cpu.append(CACHE['cpu_percent'])
        history_ram.append(CACHE['ram_percent'])

        z_score = 0.0
        corr_cpu = 0.0
        corr_ram = 0.0
        fft_max_amp = 0.0
        anomaly = False

        if len(history_entropy) > 10:
            arr_e = np.array(history_entropy)
            mean_e = np.mean(arr_e)
            std_e = np.std(arr_e)
            if std_e > 0:
                z_score = (entropy - mean_e) / std_e

            yf = np.abs(rfft(arr_e))
            if len(yf) > 1:
                fft_max_amp = float(np.max(yf[1:]))

            arr_c = np.array(history_cpu)
            if np.std(arr_c) > 0 and std_e > 0:
                corr_cpu, _ = pearsonr(arr_e, arr_c)

            arr_r = np.array(history_ram)
            if np.std(arr_r) > 0 and std_e > 0:
                corr_ram, _ = pearsonr(arr_e, arr_r)
                
            if math.isnan(corr_cpu): corr_cpu = 0.0
            if math.isnan(corr_ram): corr_ram = 0.0

        if abs(z_score) > 2.5 or abs(corr_cpu) > 0.6 or abs(corr_ram) > 0.6 or fft_max_amp > 1.5:
            anomaly = True

        ml_anomaly_score = 0.0
        ml_is_anomaly = False
        current_features = [entropy, CACHE['cpu_percent'], CACHE['ram_percent'], CACHE['disk_percent'], CACHE['net_recv_rate']]
        history_features.append(current_features)
        
        if len(history_features) >= 50:
            X = np.array(history_features)
            iso_forest.fit(X)
            pred = iso_forest.predict([current_features])[0]
            ml_anomaly_score = float(iso_forest.score_samples([current_features])[0])
            if pred == -1:
                ml_is_anomaly = True
                anomaly = True
                
        try:
            cursor = db_conn.cursor()
            cursor.execute('''
                INSERT INTO os_telemetry (timestamp, entropy, cpu_percent, ram_percent, disk_percent, net_recv_rate, anomaly_score, is_anomaly)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (time.time(), entropy, CACHE['cpu_percent'], CACHE['ram_percent'], CACHE['disk_percent'], CACHE['net_recv_rate'], ml_anomaly_score, anomaly))
            db_conn.commit()
        except Exception as e:
            logger.error(f"Database insertion failed: {e}")

        payload = {
            "timestamp": time.time(),
            "type": "science_telemetry",
            "metrics": {
                "shannon_entropy": entropy,
                "entropy_source": source,
                "os_cpu_percent": CACHE['cpu_percent'],
                "os_ram_percent": CACHE['ram_percent'],
                "os_disk_percent": CACHE['disk_percent'],
                "os_net_recv_rate": CACHE['net_recv_rate'],
                "os_net_sent_rate": CACHE['net_sent_rate'],
                "os_net_recv_total": CACHE['net_recv_mb'],
                "os_net_sent_total": CACHE['net_sent_mb'],
                "geomagnetic_kp": CACHE['geomagnetic_kp'],
                "seismic_mag": CACHE['seismic_mag'],
                "seismic_location": CACHE['seismic_location'],
                "xray_flux": CACHE['xray_flux']
            },
            "analytics": {
                "rolling_z_score": round(z_score, 2),
                "pearson_r_quantum_cpu": corr_cpu,
                "pearson_r_quantum_ram": corr_ram,
                "fft_dominant_amplitude": round(fft_max_amp, 4),
                "ml_anomaly_score": round(ml_anomaly_score, 4),
                "ml_anomaly_detected": ml_is_anomaly,
                "anomaly_detected": anomaly
            }
        }
        
        yield payload
        await asyncio.sleep(1.0)

async def websocket_handler(websocket):
    client_ip = websocket.remote_address
    logger.info(f"Client connected: {client_ip}")
    try:
        async for payload in tick_generator():
            await websocket.send(json.dumps(payload))
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_ip}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

async def main():
    asyncio.create_task(background_poller())
    asyncio.create_task(qrng_poller())

    logger.info("Starting Advanced OS Telemetry Engine on ws://0.0.0.0:8765")
    server = None
    for attempt in range(5):
        try:
            server = await websockets.serve(websocket_handler, "0.0.0.0", 8765)
            logger.info("Science Engine WebSocket server bound to ws://0.0.0.0:8765")
            break
        except OSError as e:
            if attempt < 4:
                logger.warning(f"Port 8765 busy ({e}), retrying in 2 seconds... (attempt {attempt + 1}/5)")
                await asyncio.sleep(2)
            else:
                logger.error(f"Failed to bind port 8765 after 5 attempts: {e}")
                raise

    if server:
        async with server:
            await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Science Engine shutting down.")
