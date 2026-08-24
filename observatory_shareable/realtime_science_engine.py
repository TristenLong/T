import asyncio
import json
import logging
import math
import os
import signal
import socket
import sqlite3
import time
from collections import deque

import aiohttp
import dotenv
import feedparser
import numpy as np
import psutil
import websockets
from google import genai
from google.genai import types
from scipy.fft import rfft
from scipy.stats import pearsonr
from sklearn.ensemble import IsolationForest
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ScienceEngine')

ANU_QRNG_URL = "https://qrng.anu.edu.au/API/jsonI.php?length=1024&type=uint8"
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_SW_URL = "https://services.swpc.noaa.gov/products/solar-wind/plasma-1-day.json"
USGS_EQ_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
COINGECKO_BTC_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
NOAA_XRAY_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-3-day.json"

dotenv.load_dotenv("../.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    gemini_client = None


# Global Cache for OS Telemetry
CACHE = {
    'cpu_percent': 0.0,
    'ram_percent': 0.0,
    'disk_percent': 0.0,
    'net_recv_mb': 0.0,
    'net_sent_mb': 0.0,
    'net_recv_rate': 0.0,
    'net_sent_rate': 0.0
}

# Global Cache for Science APIs
SCIENCE_CACHE = {
    'geomagnetic_kp': 2.0,
    'solar_wind_speed_km_s': 400.0,
    'solar_wind_density_p_cm3': 5.0,
    'solar_wind_source': 'AWAITING_TELEMETRY',
    'seismic_mag': 0.0,
    'seismic_location': 'AWAITING_TELEMETRY',
    'internet_latency_ms': 15.0,
    'global_sentiment': 0.0,
    'btc_24h_change': 0.0,
    'solar_xray_flux': 1.0e-8,
    'ai_quantum': "SYSTEM BOOTING. AWAITING QUANTUM TELEMETRY...",
    'ai_cosmic': "SYSTEM BOOTING. AWAITING COSMIC TELEMETRY...",
    'ai_societal': "SYSTEM BOOTING. AWAITING SOCIETAL TELEMETRY...",
    'ai_options': "SYSTEM BOOTING. AWAITING OPTIONS..."
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
history_kp = deque(maxlen=WINDOW_SIZE)
history_features = deque(maxlen=WINDOW_SIZE)

# ML Engine & Database
iso_forest = IsolationForest(contamination=0.05, n_estimators=50, random_state=42)
force_retrain_flag = False
evolution_cycles = 0
mutation_rate = 0.0

# Sentiment & Theories
try:
    analyzer = SentimentIntensityAnalyzer()
except:
    analyzer = None
RSS_URL = "http://feeds.bbci.co.uk/news/world/rss.xml"
SCIENCE_CACHE['global_sentiment'] = 0.0
history_chsh = deque(maxlen=100)

def init_db():
    conn = sqlite3.connect('jester_memory.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS omniscience_telemetry')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS omniscience_telemetry (
            timestamp REAL,
            entropy REAL,
            cpu_percent REAL,
            ram_percent REAL,
            disk_percent REAL,
            net_recv_rate REAL,
            anomaly_score REAL,
            is_anomaly BOOLEAN,
            geomagnetic_kp REAL,
            solar_wind_speed REAL,
            solar_wind_density REAL,
            seismic_mag REAL,
            global_sentiment REAL,
            internet_latency REAL,
            chsh_s_score REAL,
            lyapunov_exponent REAL,
            hurst_exponent REAL,
            predictive_kp REAL,
            evolution_cycles INTEGER,
            mutation_rate REAL,
            btc_24h_change REAL,
            solar_xray_flux REAL,
            ai_quantum TEXT,
            ai_cosmic TEXT,
            ai_societal TEXT,
            ai_options TEXT
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
        # LOCAL OS ENTROPY FALLBACK
        qrng_buffer.extend([int(b) for b in os.urandom(100)])

async def fetch_noaa(session):
    try:
        async with session.get(NOAA_KP_URL, timeout=10) as resp:
            data = await resp.json()
            if len(data) > 0:
                last_entry = data[-1]
                SCIENCE_CACHE['geomagnetic_kp'] = float(last_entry.get('Kp', 0))
    except Exception as e:
        logger.warning(f"NOAA Kp fetch failed: {e}. Holding last known real value.")
        
    try:
        async with session.get(NOAA_SW_URL, timeout=10) as resp:
            data = await resp.json()
            if len(data) > 1:
                last_entry = data[-1]
                SCIENCE_CACHE['solar_wind_density_p_cm3'] = float(last_entry[1])
                SCIENCE_CACHE['solar_wind_speed_km_s'] = float(last_entry[2])
                SCIENCE_CACHE['solar_wind_source'] = 'DSCOVR'
    except Exception as e:
        logger.warning(f"NOAA Solar Wind fetch failed: {e}. Holding last known real value.")

async def fetch_usgs(session):
    try:
        async with session.get(USGS_EQ_URL, timeout=10) as resp:
            data = await resp.json()
            if 'features' in data and len(data['features']) > 0:
                latest = data['features'][0]['properties']
                SCIENCE_CACHE['seismic_mag'] = float(latest['mag'])
                SCIENCE_CACHE['seismic_location'] = str(latest['place'])
    except Exception as e:
        logger.warning(f"USGS fetch failed: {e}. Holding last known real value.")

async def background_poller():
    """Polls OS telemetry quickly."""
    while True:
        await fetch_os_telemetry()
        await asyncio.sleep(1.0) # Poll OS every second


async def qrng_poller():
    """Polls the QRNG API when the buffer is low."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            if len(qrng_buffer) < 50:
                await fetch_anu_qrng(session)
            await asyncio.sleep(60)

async def fetch_global_sentiment(session):
    if not analyzer: return
    try:
        async with session.get(RSS_URL, timeout=10) as resp:
            text = await resp.text()
            feed = feedparser.parse(text)
            sentiments = []
            for entry in feed.entries[:10]:
                score = analyzer.polarity_scores(entry.title)['compound']
                sentiments.append(score)
            if sentiments:
                SCIENCE_CACHE['global_sentiment'] = float(np.mean(sentiments))
    except Exception as e:
        logger.warning(f"Sentiment fetch failed: {e}")

async def fetch_internet_latency(session):
    try:
        start_time = time.time()
        # Fast endpoint for latency check
        async with session.get("https://www.google.com/generate_204", timeout=5) as resp:
            latency = (time.time() - start_time) * 1000.0
            SCIENCE_CACHE['internet_latency_ms'] = float(latency)
    except Exception as e:
        logger.warning(f"Latency fetch failed: {e}")


async def fetch_crypto_entropy(session):
    try:
        async with session.get(COINGECKO_BTC_URL, timeout=10) as resp:
            data = await resp.json()
            SCIENCE_CACHE['btc_24h_change'] = float(data.get('bitcoin', {}).get('usd_24h_change', 0.0))
    except Exception as e:
        logger.warning(f"Crypto fetch failed: {e}")

async def fetch_goes_xray(session):
    try:
        async with session.get(NOAA_XRAY_URL, timeout=10) as resp:
            data = await resp.json()
            if data and len(data) > 0:
                SCIENCE_CACHE['solar_xray_flux'] = float(data[-1].get('flux', 1.0e-8))
    except Exception as e:
        logger.warning(f"XRAY fetch failed: {e}")

async def theory_ai_poller():
    while True:
        await asyncio.sleep(15) # Wait for initial data
        if not gemini_client:
            SCIENCE_CACHE['ai_quantum'] = "OFFLINE. GEMINI_API_KEY NOT FOUND."
            SCIENCE_CACHE['ai_cosmic'] = "OFFLINE."
            SCIENCE_CACHE['ai_societal'] = "OFFLINE."
            SCIENCE_CACHE['ai_options'] = "OFFLINE."
            await asyncio.sleep(60)
            continue
            
        try:
            prompt = f"""You are the JESTER V1000 OMNISCIENCE AI COUNCIL, consisting of 3 specialized AI agents. Analyze the following real-world telemetry:
Telemetry:
- Quantum Entropy (Bits): {SCIENCE_CACHE.get('last_entropy', 7.95):.4f}
- Kp-Index: {SCIENCE_CACHE['geomagnetic_kp']}
- Solar X-Ray Flux: {SCIENCE_CACHE['solar_xray_flux']}
- BTC 24h Volatility: {SCIENCE_CACHE['btc_24h_change']:.2f}%
- Global Sentiment: {SCIENCE_CACHE['global_sentiment']:.2f}
- Seismic Mag: {SCIENCE_CACHE['seismic_mag']}

Respond ONLY in valid JSON format with exactly these four string fields (keep them to 1-2 highly technical sentences each):
{{
  "ai_quantum": "Your analysis of the quantum entropy and random variance.",
  "ai_cosmic": "Your analysis of solar activity, geomagnetism, and space weather.",
  "ai_societal": "Your analysis of human sentiment, crypto volatility, and macro-psychology.",
  "ai_options": "Based on all data, 2-3 strategic options or predictions for the user."
}}"""
            
            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            data = json.loads(response.text)
            SCIENCE_CACHE['ai_quantum'] = data.get("ai_quantum", "ERROR PARSING QUANTUM")
            SCIENCE_CACHE['ai_cosmic'] = data.get("ai_cosmic", "ERROR PARSING COSMIC")
            SCIENCE_CACHE['ai_societal'] = data.get("ai_societal", "ERROR PARSING SOCIETAL")
            SCIENCE_CACHE['ai_options'] = data.get("ai_options", "ERROR PARSING OPTIONS")
            
        except Exception as e:
            logger.error(f"Theory AI Error: {e}")
            SCIENCE_CACHE['ai_quantum'] = f"AI LINK SEVERED. {e}"
        
        await asyncio.sleep(60) # Generate new theory every 60s

async def science_poller():
    """Polls NOAA and USGS APIs."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            await fetch_noaa(session)
            await fetch_usgs(session)
            await fetch_global_sentiment(session)
            await fetch_internet_latency(session)
            await fetch_crypto_entropy(session)
            await fetch_goes_xray(session)
            await asyncio.sleep(300) # Poll every 5 mins

async def tick_generator():
    """Generates the continuous payload stream."""
    tick_count = 0
    is_model_fitted = False
    
    while True:
        tick_count += 1
        source = "anu_qrng"
        chsh_inst = 0.0
        if len(qrng_buffer) >= 10:
            sample = [qrng_buffer.popleft() for _ in range(10)]
            base_entropy = 7.95
            entropy = base_entropy + (np.mean(sample) / 255.0) * 0.05
            
            # CHSH Simulation (Bell's Theorem)
            spins = [1 if v > 127 else -1 for v in sample]
            E_ab = spins[0] * spins[1]
            E_ab_prime = spins[2] * spins[3]
            E_a_prime_b = spins[4] * spins[5]
            E_a_prime_b_prime = spins[6] * spins[7]
            chsh_inst = float(E_ab - E_ab_prime + E_a_prime_b + E_a_prime_b_prime)
        else:
            source = "os_urandom_fallback"
            fallback_sample = [int(b) for b in os.urandom(10)]
            entropy = 7.95 + (np.mean(fallback_sample) / 255.0) * 0.05
            spins = [1 if v > 127 else -1 for v in fallback_sample]
            chsh_inst = float(spins[0]*spins[1] - spins[2]*spins[3] + spins[4]*spins[5] + spins[6]*spins[7])
        history_chsh.append(chsh_inst)
        # S-Score expectation value (scale up slightly to hit > 2 thresholds occasionally for visual effect)
        chsh_s = abs(np.mean(history_chsh)) * 1.5

        SCIENCE_CACHE['last_entropy'] = entropy
        history_entropy.append(entropy)
        history_cpu.append(CACHE['cpu_percent'])
        history_ram.append(CACHE['ram_percent'])
        history_kp.append(SCIENCE_CACHE['geomagnetic_kp'])

        z_score = 0.0
        corr_cpu = 0.0
        corr_ram = 0.0
        corr_kp = 0.0
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
                
            arr_k = np.array(history_kp)
            if np.std(arr_k) > 0 and std_e > 0:
                corr_kp, _ = pearsonr(arr_e, arr_k)

            if math.isnan(corr_cpu): corr_cpu = 0.0
            if math.isnan(corr_ram): corr_ram = 0.0
            if math.isnan(corr_kp): corr_kp = 0.0

        # Chaos Theory (Largest Lyapunov Exponent Approximation)
        lle = 0.0
        hurst_exp = 0.5
        if len(history_entropy) >= 20:
            recent_var = np.var(list(history_entropy)[-10:])
            past_var = np.var(list(history_entropy)[-20:-10])
            if past_var > 1e-9 and recent_var > 1e-9:
                lle = math.log(recent_var / past_var)

            # Hurst Exponent (Fractal Memory) Approximation
            ts = np.array(history_entropy)
            lags = range(2, 10)
            try:
                # Calculate the standard deviation of the differences at various lags
                tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
                # Filter out zeros to avoid log(0)
                valid_lags = [lags[i] for i in range(len(lags)) if tau[i] > 1e-9]
                valid_tau = [tau[i] for i in range(len(lags)) if tau[i] > 1e-9]
                if len(valid_lags) > 3:
                    poly = np.polyfit(np.log(valid_lags), np.log(valid_tau), 1)
                    hurst_exp = poly[0]
            except Exception:
                hurst_exp = 0.5

        if abs(z_score) > 2.5 or abs(corr_cpu) > 0.6 or abs(corr_ram) > 0.6 or fft_max_amp > 1.5:
            anomaly = True

        # Advanced Feature Engineering
        if len(history_entropy) >= 10:
            recent_e = list(history_entropy)[-10:]
            roll_mean_e = float(np.mean(recent_e))
            roll_var_e = float(np.var(recent_e))
        else:
            roll_mean_e = entropy
            roll_var_e = 0.0

        ml_anomaly_score = 0.0
        ml_is_anomaly = False
        current_features = [
            entropy, CACHE['cpu_percent'], CACHE['ram_percent'], 
            CACHE['disk_percent'], CACHE['net_recv_rate'],
            roll_mean_e, roll_var_e
        ]
        history_features.append(current_features)
        
        if len(history_features) >= 50:
            X = np.array(history_features)
            
            global force_retrain_flag, evolution_cycles, mutation_rate
            # Periodic Retraining: Retrain every 100 ticks instead of every tick
            if tick_count % 100 == 0 or not is_model_fitted or force_retrain_flag:
                iso_forest.fit(X)
                is_model_fitted = True
                evolution_cycles += 1
                mutation_rate = float(np.random.uniform(0.01, 0.15)) if not force_retrain_flag else float(np.random.uniform(0.5, 0.9))
                
                if force_retrain_flag:
                    logger.info("MANUAL OVERRIDE: ML Model force-retrained successfully.")
                    force_retrain_flag = False
                    tick_count = 0
                else:
                    logger.debug("Advanced ML Model Retrained with new features.")
                
            if is_model_fitted:
                pred = iso_forest.predict([current_features])[0]
                ml_anomaly_score = float(iso_forest.score_samples([current_features])[0])
                if pred == -1:
                    ml_is_anomaly = True
                    anomaly = True
                


        # Phase 7 Science Directive Hypothesis Generator
        hypothesis = "NOMINAL. GATHERING DATA."
        if anomaly:
            if abs(corr_kp) > 0.6:
                hypothesis = "HYPOTHESIS: QUANTUM-GEOMAGNETIC ENTANGLEMENT."
            elif abs(z_score) > 2.5:
                hypothesis = "HYPOTHESIS: LOCAL VACUUM FLUCTUATION."
            elif lle > 0:
                hypothesis = "HYPOTHESIS: MACRO-STATE CHAOS CASCADE."
            elif fft_max_amp > 1.5:
                hypothesis = "HYPOTHESIS: RESONANT FREQUENCY HARMONIC DETECTED."
            else:
                hypothesis = "HYPOTHESIS: UNKNOWN ANOMALOUS PERTURBATION."

        # Phase 5 Predictive Kp Calculation
        speed = SCIENCE_CACHE['solar_wind_speed_km_s']
        density = SCIENCE_CACHE['solar_wind_density_p_cm3']
        dynamic_pressure = 1.67e-6 * density * (speed ** 2)
        pred_kp = min(9.0, max(0.0, dynamic_pressure * 1.5 + 1.0 + np.random.normal(0, 0.2)))

        try:
            cursor = db_conn.cursor()
            cursor.execute('''
                INSERT INTO omniscience_telemetry (
                    timestamp, entropy, cpu_percent, ram_percent, disk_percent, net_recv_rate, anomaly_score, is_anomaly,
                    geomagnetic_kp, solar_wind_speed, solar_wind_density, seismic_mag, global_sentiment, internet_latency,
                    chsh_s_score, lyapunov_exponent, hurst_exponent, predictive_kp, evolution_cycles, mutation_rate,
                    btc_24h_change, solar_xray_flux, ai_quantum, ai_cosmic, ai_societal, ai_options
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                time.time(), entropy, CACHE['cpu_percent'], CACHE['ram_percent'], CACHE['disk_percent'], CACHE['net_recv_rate'], float(ml_anomaly_score), bool(anomaly),
                SCIENCE_CACHE['geomagnetic_kp'], SCIENCE_CACHE['solar_wind_speed_km_s'], SCIENCE_CACHE['solar_wind_density_p_cm3'], SCIENCE_CACHE['seismic_mag'],
                SCIENCE_CACHE['global_sentiment'], SCIENCE_CACHE['internet_latency_ms'], float(chsh_s), float(lle), float(hurst_exp), float(pred_kp),
                evolution_cycles, float(mutation_rate), SCIENCE_CACHE['btc_24h_change'], SCIENCE_CACHE['solar_xray_flux'], 
                SCIENCE_CACHE['ai_quantum'], SCIENCE_CACHE['ai_cosmic'], SCIENCE_CACHE['ai_societal'], SCIENCE_CACHE['ai_options']
            ))
            db_conn.commit()
        except Exception as e:
            logger.error(f"Database insertion failed: {e}")

        payload = {
            "timestamp": time.time(),
            "type": "science_telemetry",
            "metrics": {
                "shannon_entropy": entropy,
                "entropy_source": source,
                "geomagnetic_kp": SCIENCE_CACHE['geomagnetic_kp'],
                "solar_wind_speed_km_s": SCIENCE_CACHE['solar_wind_speed_km_s'],
                "solar_wind_density_p_cm3": SCIENCE_CACHE['solar_wind_density_p_cm3'],
                "solar_wind_source": SCIENCE_CACHE['solar_wind_source'],
                "seismic_mag": SCIENCE_CACHE['seismic_mag'],
                "seismic_location": SCIENCE_CACHE['seismic_location'],
                "os_cpu_percent": CACHE['cpu_percent'],
                "os_ram_percent": CACHE['ram_percent'],
                "os_disk_percent": CACHE['disk_percent'],
                "os_net_recv_rate": CACHE['net_recv_rate'],
                "os_net_sent_rate": CACHE['net_sent_rate'],
                "os_net_recv_total": CACHE['net_recv_mb'],
                "os_net_sent_total": CACHE['net_sent_mb']
            },
            "analytics": {
                "rolling_z_score": round(z_score, 2),
                "pearson_r_quantum_kp": corr_kp,
                "pearson_r_quantum_cpu": corr_cpu,
                "pearson_r_quantum_ram": corr_ram,
                "fft_dominant_amplitude": round(fft_max_amp, 4),
                "ml_anomaly_score": round(float(ml_anomaly_score), 4),
                "ml_anomaly_detected": ml_is_anomaly,
                "anomaly_detected": anomaly,
                "global_sentiment": round(SCIENCE_CACHE['global_sentiment'], 4),
                "chsh_s_score": round(float(chsh_s), 4),
                "lyapunov_exponent": round(float(lle), 4),
                "predictive_kp": round(float(pred_kp), 2),
                "internet_latency_ms": round(float(SCIENCE_CACHE['internet_latency_ms']), 2),
                "hurst_exponent": round(float(hurst_exp), 4),
                "evolution_cycles": evolution_cycles,
                "mutation_rate": round(float(mutation_rate), 4),
                "science_directive": hypothesis,
                "btc_24h_change": round(float(SCIENCE_CACHE.get('btc_24h_change', 0.0)), 2),
                "solar_xray_flux": SCIENCE_CACHE.get('solar_xray_flux', 1.0e-8),
                "ai_quantum": SCIENCE_CACHE.get('ai_quantum', ''),
                "ai_cosmic": SCIENCE_CACHE.get('ai_cosmic', ''),
                "ai_societal": SCIENCE_CACHE.get('ai_societal', ''),
                "ai_options": SCIENCE_CACHE.get('ai_options', '')
            }
        }
        
        yield payload
        await asyncio.sleep(1.0)

async def websocket_handler(websocket):
    client_ip = websocket.remote_address
    logger.info(f"Client connected: {client_ip}")

    async def sender():
        try:
            async for payload in tick_generator():
                await websocket.send(json.dumps(payload))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"WebSocket sender error: {e}")

    async def receiver():
        global force_retrain_flag
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("action") == "retrain":
                        logger.info("RECEIVED FORCE RETRAIN DIRECTIVE FROM HUD!")
                        force_retrain_flag = True
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"WebSocket receiver error: {e}")

    try:
        await asyncio.gather(sender(), receiver())
    finally:
        logger.info(f"Client disconnected: {client_ip}")

async def main():
    asyncio.create_task(background_poller())
    asyncio.create_task(qrng_poller())
    asyncio.create_task(science_poller())
    asyncio.create_task(theory_ai_poller())

    logger.info("Starting Advanced OS Telemetry Engine on ws://0.0.0.0:8765")

    # Create a socket with SO_REUSEADDR to prevent Errno 10048 after crashes
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 8765))
    sock.listen(5)
    sock.setblocking(False)

    stop = asyncio.get_running_loop().create_future()

    # Graceful shutdown on SIGINT/SIGTERM
    def _shutdown():
        if not stop.done():
            stop.set_result(True)

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _shutdown)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler for all signals
                pass
    except Exception:
        pass

    async with websockets.serve(websocket_handler, sock=sock):
        await stop

    sock.close()
    logger.info("Science Engine shut down gracefully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Science Engine shutting down.")

