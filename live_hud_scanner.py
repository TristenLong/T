import asyncio
import websockets
import json
import os
import sys
import collections
import numpy as np

# A simple terminal HUD that connects to the engine
# And runs real-time anomaly scanning algorithms

history = collections.deque(maxlen=50)

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def scan_anomalies(data):
    metrics = data.get('metrics', {})
    entropy = metrics.get('shannon_entropy', 0)
    history.append(entropy)
    
    warnings = []
    
    # Algo 1: Rapid Derivative Change
    if len(history) > 2:
        diff = history[-1] - history[-2]
        if abs(diff) > 0.08:
            warnings.append(f"RAPID ENTROPY SHIFT: {diff:.4f}")
            
    # Algo 2: Local Outlier Factor (Simplified Z-Score)
    if len(history) > 10:
        arr = np.array(history)
        mean = np.mean(arr)
        std = np.std(arr)
        if std > 0:
            z = (entropy - mean) / std
            if abs(z) > 2.0:
                warnings.append(f"STATISTICAL ANOMALY DETECTED (Z-SCORE: {z:.2f} \u03c3)")
                
    # Algo 3: Cross-domain correlation check (using pre-calculated backend analytics)
    analytics = data.get("analytics", {})
    if analytics.get("anomaly_detected"):
        warnings.append("MACRO-STATE ANOMALY DETECTED BY CORE ENGINE")
        
    # Algo 4: FFT Dominant Amplitude Check
    fft_amp = analytics.get("fft_dominant_amplitude", 0)
    if fft_amp > 1.5:
        warnings.append(f"REPEATING QUANTUM FREQUENCY DETECTED (FFT Amp: {fft_amp:.2f})")
                
    return warnings

async def hud_loop():
    uri = "ws://localhost:8765"
    while True:
        try:
            async with websockets.connect(uri) as ws:
                while True:
                    message = await ws.recv()
                    data = json.loads(message)
                    
                    clear_console()
                    
                    print("\033[92m") # Matrix Green
                    print("="*70)
                    print("||               OMNISCIENCE LIVE TELEMETRY HUD                 ||")
                    print("="*70)
                    
                    metrics = data.get("metrics", {})
                    analytics = data.get("analytics", {})
                    
                    print("\n[ DATA SOURCES ]")
                    print(f" >> Quantum Entropy: {metrics.get('entropy_source').upper()}")
                    print(f" >> Space Weather:   NOAA DSCOVR SATELLITE")
                    print(f" >> Tectonics:       USGS REALTIME SEISMIC")
                    
                    print("\n----------------------------------------------------------------------")
                    print(f" [ QUANTUM ] Shannon Entropy:    {metrics.get('shannon_entropy', 0):.6f} bits")
                    print(f" [ GEOMAG  ] Planetary K-Idx:    {metrics.get('geomagnetic_kp', 0)}  |  Mag Bt: {metrics.get('magnetometer_bt', 0):.2f} nT")
                    print(f" [ S-WIND  ] Speed / Density:    {metrics.get('solar_wind_speed_km_s', 0):.1f} km/s | {metrics.get('solar_wind_density_p_cm3', 0):.1f} p/cm3")
                    print(f" [ X-RAY   ] Solar Flare Flux:   {metrics.get('xray_flux', 0):.2e} W/m2")
                    print(f" [ SEISMIC ] Largest Quake (4+): M{metrics.get('seismic_mag', 0)} ({metrics.get('seismic_location', '')})")
                    print("----------------------------------------------------------------------")
                    
                    warnings = scan_anomalies(data)
                    print("\n [ ACTIVE SCANNERS & ANOMALY ALGORITHMS ]")
                    print(" Running: Rapid Shift Detector, Micro-Outlier Z-Score, FFT Fast Fourier Transform")
                    print("")
                    
                    if warnings:
                        for w in warnings:
                            print(f"   \033[91m[!] WARNING: {w}\033[92m")
                    else:
                        print(f"   >> ALL DATA STREAMS STABLE. NO ANOMALIES DETECTED.")
                        
                    print("\n="*70)
                    print("\033[0m") # Reset color
                    
        except Exception as e:
            clear_console()
            print(f"CONNECTION LOST TO CORE ENGINE. RETRYING... ({e})")
            await asyncio.sleep(2)

if __name__ == '__main__':
    # Initialize color output on windows
    os.system('color')
    try:
        asyncio.run(hud_loop())
    except KeyboardInterrupt:
        print("HUD offline.")
