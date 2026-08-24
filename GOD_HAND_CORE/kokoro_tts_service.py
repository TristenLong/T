import os
from typing import AsyncGenerator

import numpy as np
from loguru import logger
from pipecat.frames.frames import AudioRawFrame, ErrorFrame, Frame
from pipecat.services.ai_services import TTSService

try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None

class KokoroTTSService(TTSService):
    def __init__(self, 
                 model_path: str = "models/kokoro-v1.0.onnx", 
                 voices_path: str = "models/voices.json", 
                 voice: str = "af_heart",
                 sample_rate: int = 24000,
                 **kwargs):
        super().__init__(**kwargs)
        
        if not Kokoro:
            raise ImportError("kokoro-onnx is not installed. Please install it to use KokoroTTSService.")
            
        self.model_path = model_path
        self.voices_path = voices_path
        self.voice = voice
        self.sample_rate = sample_rate
        
        if not os.path.exists(self.model_path) or not os.path.exists(self.voices_path):
            logger.warning(f"Kokoro models not found at {self.model_path} or {self.voices_path}. Downloading...")
            from download_kokoro_models import download_kokoro
            download_kokoro()
            
        logger.info(f"Loading Kokoro TTS engine with voice: {self.voice}")
        self.kokoro = Kokoro(self.model_path, self.voices_path)
        logger.info("Kokoro engine initialized.")

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        try:
            # Generate raw audio data (returns float32 array and sample rate)
            # kokoro-onnx returns (audio_array, sample_rate)
            samples, sr = self.kokoro.create(text, voice=self.voice, speed=1.0, lang="en-us")
            
            # Convert float32 [-1.0, 1.0] to int16
            audio_int16 = (samples * 32767.0).astype(np.int16)
            
            # Yield in chunks for Pipecat's streaming transport
            chunk_size = 4096
            for i in range(0, len(audio_int16), chunk_size):
                chunk = audio_int16[i:i+chunk_size]
                yield AudioRawFrame(audio=chunk.tobytes(), sample_rate=sr, num_channels=1)
                
        except Exception as e:
            logger.error(f"Kokoro TTS generation failed: {e}")
            yield ErrorFrame(f"Kokoro TTS Error: {str(e)}")
