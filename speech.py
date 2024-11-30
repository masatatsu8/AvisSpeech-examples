import sys
import io
import json
import requests
import pyaudio
import numpy as np
import threading
import asyncio

def play_audio(audio_data, sample_rate=44100):
    pya = pyaudio.PyAudio()
    stream = pya.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        output=True,
        frames_per_buffer=128,
    )
    
    # 最小限の無音データを書き込んでバッファを準備
    silence = np.zeros(128, dtype=np.int16)
    stream.write(silence.tobytes())
    
    # チャンク単位で音声データを書き込む
    chunk_size = 128
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i + chunk_size]
        stream.write(chunk.tobytes())
    
    stream.stop_stream()
    stream.close()
    pya.terminate()

async def speech(text, host='127.0.0.1', port=10101, speaker=888753760):
    params = {
        'text': text,
        'speaker': speaker,
    }
    query = requests.post(
        f'http://{host}:{port}/audio_query',
        params=params,
    )
    data = query.json()
    
    synthesis = requests.post(
        f'http://{host}:{port}/synthesis',
        headers={'Content-Type': 'application/json'},
        params=params,
        data=json.dumps(data),
    )
    voice = synthesis.content

    # 音声データをnumpy配列に変換
    audio_data = np.frombuffer(voice, dtype=np.int16).copy()
    
    # フェードイン用のカーブを作成（最初の10msに適用）
    sample_rate = 44100
    fade_duration = 0.01  # 10ms
    fade_length = int(fade_duration * sample_rate)
    fade_curve = np.linspace(0, 1, fade_length)
    
    # フェードインを適用
    if len(audio_data) > fade_length:
        audio_data[:fade_length] = audio_data[:fade_length] * fade_curve
    
    # 別スレッドで音声を再生
    thread = threading.Thread(target=play_audio, args=(audio_data,))
    thread.start()
    
    # すぐに制御を返す
    return thread

