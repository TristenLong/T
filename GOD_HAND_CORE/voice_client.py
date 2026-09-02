import asyncio
import os

import edge_tts
import google.generativeai as genai
import numpy as np
import pygame
import scipy.io.wavfile as wav
import sounddevice as sd
import speech_recognition as sr
from dotenv import load_dotenv

# 1. Setup Gemini
load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    print("Error: GEMINI_API_KEY not found in .env file.")
    # Attempt to read from server.py if .env is missing or empty
    try:
        server_path = os.path.join(os.path.dirname(__file__), 'server.py')
        with open(server_path, 'r') as f:
            for line in f:
                if 'API_KEY = os.getenv' in line:
                    continue
                if 'API_KEY =' in line and '"' in line:
                    API_KEY = line.split('"')[1]
                    break
                if "API_KEY =" in line and "'" in line:
                    API_KEY = line.split("'")[1]
                    break
    except Exception:
        pass

if not API_KEY or API_KEY == "YOUR_FREE_API_KEY":
    print("CRITICAL: Please set GEMINI_API_KEY in .env")
    exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# Initialize Pygame Mixer for Audio
try:
    pygame.mixer.init()
except Exception as e:
    print(f"Warning: Audio output init failed: {e}")

def play_audio(file_path):
    try:
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
    except Exception as e:
        print(f"Audio Playback Error: {e}")
        # Fallback to system player
        try:
            os.system(f'start {file_path}')
        except Exception:
            pass

def record_audio_fallback(duration=5, fs=44100):
    print(f"  [Recording {duration}s via SoundDevice...]")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # Wait until recording is finished
    wav.write('temp_input.wav', fs, recording)
    return 'temp_input.wav'

def listen_mic():
    r = sr.Recognizer()
    
    # Check if PyAudio is available for sr.Microphone
    use_fallback = False
    try:
        with sr.Microphone() as source:
            pass
    except (ImportError, AttributeError, OSError):
        use_fallback = True
        print("\n[NOTE] PyAudio not found. Using SoundDevice fallback (fixed 5s recording).")

    if not use_fallback:
        try:
            with sr.Microphone() as source:
                print("\n[LISTENING] Waiting for voice input...")
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=5, phrase_time_limit=10)
                print("[RECOGNIZING]...")
                text = r.recognize_google(audio)
                print(f"You said: {text}")
                return text
        except sr.WaitTimeoutError:
            print("[SILENCE]...")
            return None
        except sr.UnknownValueError:
            print("[UNKNOWN]...")
            return None
        except Exception as e:
            print(f"[ERROR] Microphone error: {e}")
            return None
    else:
        # Fallback path
        try:
            print("\n[LISTENING] Recording 5 seconds...")
            file_path = record_audio_fallback()
            with sr.AudioFile(file_path) as source:
                audio = r.record(source)
                print("[RECOGNIZING]...")
                text = r.recognize_google(audio)
                print(f"You said: {text}")
                os.remove(file_path)
                return text
        except Exception as e:
            print(f"[ERROR] Fallback recording error: {e}")
            return None

# 2. The Matrix Loop
async def run_matrix():
    print("Matrix Voice Interface Online. Press Ctrl+C to exit.")
    
    # Clean up
    for temp_file in ["reply.mp3", "temp_input.wav"]:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

    while True:
        user_text = listen_mic() 
        
        if user_text:
            if user_text.lower() in ["exit", "quit", "stop", "terminate"]:
                print("Matrix Connection Terminated.")
                break

            try:
                # Send text to Gemini
                print("[THINKING]...")
                response = model.generate_content(user_text)
                reply_text = response.text
                print(f"Matrix: {reply_text}")
                
                # Speak response
                communicate = edge_tts.Communicate(reply_text, "en-US-ChristopherNeural")
                await communicate.save("reply.mp3")
                play_audio("reply.mp3")
                
            except Exception as e:
                print(f"Matrix Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_matrix())
    except KeyboardInterrupt:
        print("\nDisconnected.")