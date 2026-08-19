import pyaudio
try:
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    print(f'Detected {numdevices} devices:')
    for i in range(0, numdevices):
        dev_info = p.get_device_info_by_host_api_device_index(0, i)
        if dev_info.get('maxInputChannels') > 0:
            print(f'  [INPUT] Index {i}: {dev_info.get('name')}')
        if dev_info.get('maxOutputChannels') > 0:
            print(f'  [OUTPUT] Index {i}: {dev_info.get('name')}')
    p.terminate()
except Exception as e:
    print(f'AUDIO_DIAGNOSTIC_ERROR: {e}')
