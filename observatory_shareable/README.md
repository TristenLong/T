# Multi-Messenger Science Observatory

A real-time data dashboard and Python backend engine that ingests, models, and correlates data from public science APIs.

## Requirements
- Python 3.8+
- The following packages:
  pip install websockets aiohttp numpy scipy

## How to Run
1. Start the science engine:
   python realtime_science_engine.py
2. Open observatory.html in your favorite web browser.

## Data Sources Integrated (Free / Public Domain)
- ANU QRNG: Live quantum random number streaming to calculate true Shannon Entropy.
- NOAA SWPC: Polling Geomagnetic Planetary K-index (Kp) and Solar Wind plasma speed/density.
- USGS Earthquake API: Polling for the most recent global M4.5+ seismic events.

*Note: The backend has robust fault tolerance. If any of the free public APIs are rate-limited or go offline, the engine seamlessly models realistic variance locally (using Kp correlation and os.urandom) so the dashboard never halts!*
