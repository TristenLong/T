import os
import asyncio
from dotenv import load_dotenv
from pipecat.services.openai.tts import OpenAITTSService
from loguru import logger

async def test_tts():
    load_dotenv('../.env')
    key = os.getenv('OPENAI_API_KEY')
    print(f'Using Key: {key[:10]}...')
    try:
        tts = OpenAITTSService(api_key=key, voice='onyx', model='tts-1')
        print('? OpenAI TTS Service Initialized!')
    except Exception as e:
        print(f'? TTS INIT FAILED: {e}')

if __name__ == '__main__':
    asyncio.run(test_tts())
