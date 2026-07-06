import os
import json
import time
import struct
import wave
import subprocess
import numpy as np
import pyaudio
from faster_whisper import WhisperModel
import asyncio
import requests
from openai import AsyncOpenAI
from openai.helpers import LocalAudioPlayer
from pathlib import Path

import tempfile

# ---- IMPORT OPENWAKEWORD ----
from openwakeword.model import Model

MAIN_DIR = Path(__file__).resolve().parent.parent.parent
SUB_PROGRAMS_DIR = os.path.join(MAIN_DIR, "sub-programs")
MASTER_DIR = os.path.join(MAIN_DIR, "master")
FILE_DIR = os.path.join(MASTER_DIR, "files")

VOICE_DIR = os.path.join(SUB_PROGRAMS_DIR, "voice")

# ---------------- TTS CONFIG ----------------
# Set this to "piper" or "openai" to pick which engine speaks the response.
TTS_ENGINE = "openai"

# --- Piper settings (only used if TTS_ENGINE == "piper") ---
PIPER_EXE = os.path.join(VOICE_DIR, "piper", "piper.exe")
PIPER_MODEL = os.path.join(VOICE_DIR, "piper", "jarvis-high.onnx")
PIPER_OUTPUT_WAV = os.path.join(VOICE_DIR, "tts_output.wav")

# --- OpenAI TTS settings (only used if TTS_ENGINE == "openai") ---
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TTS_VOICE = "alloy"

# ---------------- WEBHOOK CONFIG ----------------
WEBHOOK_URL = "http://127.0.0.1:5050/api/message"

# ---------------- CONFIG ----------------
WAKEWORD_PATH = os.path.join(VOICE_DIR, "wakeword", "genie.onnx")

RECORDED_FILE = "recorded_audio.wav"
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHANNELS = 1

# openWakeWord strictly expects 16000Hz sample rate and 1280 sample frame lengths
SAMPLE_RATE = 16000 
CHUNK_SIZE = 1280 

SILENCE_THRESHOLD = 500
SILENCE_DURATION = 0.8
MAX_RECORD_TIME = 10

# NOTE: Custom models usually need a much lower sensitivity threshold (0.1 - 0.3) to trigger reliably
SENSITIVITY = 0.5

# If nobody actually speaks above this average volume during the recording window,
# treat it as silence and skip transcription entirely (no Whisper call needed).
MIN_SPEECH_VOLUME = 150

openai = AsyncOpenAI()
response = ""
# ----------------------------------------

# Initialize openWakeWord
# Try a built-in string tag to see if it triggers on standard words
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
model_key = "hey_jarvis"

# Load Whisper model ONCE at startup. Re-loading it on every transcription call
# was the cause of the "abnormally long" STT delay.
print("Loading Whisper model...")
whisper_model = WhisperModel("small.en", compute_type="int8", device="auto")
print("Whisper model loaded.")

# Single PyAudio instance
pa = pyaudio.PyAudio()

def open_detection_stream():
    return pa.open(
        rate=SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        format=AUDIO_FORMAT,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )

def detect_wake_word(det_stream):
    try:
        # Check how many audio frames have accumulated in the Windows buffer
        available_frames = det_stream.get_read_available()
        
        # --- THE ANTI-LOOP MAGIC ---
        # If there is a massive backlog (e.g. from Whisper running), read ALL of it
        # to clear the hardware cache, but only slice out the LATEST 1280 chunk.
        if available_frames >= CHUNK_SIZE:
            data = det_stream.read(available_frames, exception_on_overflow=False)
            data = data[-CHUNK_SIZE * 2:] # Keep only the most recent 1280 samples
        else:
            # Otherwise, read normally
            data = det_stream.read(CHUNK_SIZE, exception_on_overflow=False)
            
        pcm = np.frombuffer(data, dtype=np.int16)
        vol = int(np.abs(pcm).mean())
        
        # Feed the frame into openWakeWord
        prediction = oww_model.predict(pcm)
        confidence = prediction[model_key]
        
        print(f"Vol: {vol} | Conf: {confidence:.2f} ", end="\r")  
        
        return confidence >= SENSITIVITY
    except Exception as e:
        print(f"\n[detect error] {e}")
        return False

def record_audio():
    rec_stream = pa.open(
        rate=SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        format=AUDIO_FORMAT,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )
    frames = []
    silent_chunks = 0
    max_volume = 0
    start_time = time.time()
    print("\nRecording... (speak now)")

    while time.time() - start_time < MAX_RECORD_TIME:
        try:
            data = rec_stream.read(CHUNK_SIZE, exception_on_overflow=False)
        except Exception as e:
            print(f"\n[record read error] {e}")
            break
        frames.append(data)
        volume = np.abs(np.frombuffer(data, dtype=np.int16)).mean()
        max_volume = max(max_volume, volume)
        if volume < SILENCE_THRESHOLD:
            silent_chunks += 1
        else:
            silent_chunks = 0
        if silent_chunks > (SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE):
            break

    rec_stream.stop_stream()
    rec_stream.close()

    # Save WAV
    with wave.open(RECORDED_FILE, "wb") as wf:
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(pa.get_sample_size(AUDIO_FORMAT))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames))
    print("Saved recording.")
    return max_volume

def transcribe():
    segments, _ = whisper_model.transcribe(RECORDED_FILE)
    text = " ".join([s.text for s in segments]).strip()
    return text

def play_wav_file(path):
    """Plays a WAV file back out through the default output device using the shared PyAudio instance."""
    try:
        with wave.open(path, "rb") as wf:
            out_stream = pa.open(
                format=pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            data = wf.readframes(CHUNK_SIZE)
            while data:
                out_stream.write(data)
                data = wf.readframes(CHUNK_SIZE)
            out_stream.stop_stream()
            out_stream.close()
    except Exception as e:
        print(f"\n[playback error] {e}")

def sanitize_for_piper(text):
    """Normalizes 'smart' punctuation that LLMs commonly produce into plain ASCII.
    Older eSpeak-ng/Piper builds can hard-crash (stack buffer overrun) on certain
    Unicode punctuation like curly quotes, em-dashes, and ellipses."""
    replacements = {
        "\u2018": "'", "\u2019": "'",   # ‘ ’
        "\u201c": '"', "\u201d": '"',   # “ ”
        "\u2013": "-", "\u2014": "-",   # – —
        "\u2026": "...",                # …
        "\u00a0": " ",                  # non-breaking space
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    # Strip anything else outside printable ASCII, just in case
    text = text.encode("ascii", "ignore").decode("ascii")
    return text

def speak_piper(text):
    """Synthesizes speech with a local Piper voice model and plays the resulting WAV."""
    text = sanitize_for_piper(text)
    if not text:
        return
        
    text = text.strip() + "\n"
    
    try:
        # 1. Write the text to a physical temporary file
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as temp_file:
            temp_file.write(text)
            temp_file_path = temp_file.name

        # 2. Open the file and stream it to Piper as standard input
        with open(temp_file_path, "rb") as f_in:
            result = subprocess.run(
                [PIPER_EXE, "--model", PIPER_MODEL, "--output_file", PIPER_OUTPUT_WAV],
                stdin=f_in,  # Feed the physical file instead of a memory string
                cwd=os.path.dirname(PIPER_EXE), 
                capture_output=True
            )
        
        # 3. Clean up the temporary file
        os.remove(temp_file_path)

        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="ignore").strip()
            print(f"\n[piper TTS error] exit code {result.returncode}: {stderr_text}")
            return
            
        play_wav_file(PIPER_OUTPUT_WAV)
        
    except Exception as e:
        print(f"\n[piper TTS error] {e}")
        # Ensure the temp file gets deleted even if Piper crashes
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass

async def speak_openai_async(text):
    """Streams speech from the OpenAI TTS API and plays it locally."""
    try:
        async with openai.audio.speech.with_streaming_response.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=text,
            response_format="pcm",
        ) as tts_response:
            await LocalAudioPlayer().play(tts_response)
    except Exception as e:
        print(f"\n[openai TTS error] {e}")

def speak_openai(text):
    asyncio.run(speak_openai_async(text))

def speak(text):
    """Dispatches to whichever TTS engine is configured via TTS_ENGINE."""
    if not text:
        return
    print(f"\n[Speaking via {TTS_ENGINE}]: {text}")
    if TTS_ENGINE == "piper":
        speak_piper(text)
    elif TTS_ENGINE == "openai":
        speak_openai(text)
    else:
        print(f"\n[TTS error] Unknown TTS_ENGINE '{TTS_ENGINE}', expected 'piper' or 'openai'")

def main():
    global response
    print("Listening for wake word...")
    det_stream = open_detection_stream()
    try:
        while True:
            if detect_wake_word(det_stream):
                print("\nWake word detected!")
                try:
                    det_stream.stop_stream()
                    det_stream.close()
                except Exception:
                    pass

                max_volume = record_audio()

                if max_volume < MIN_SPEECH_VOLUME:
                    print(f"\n[No speech detected, volume {max_volume:.0f} below threshold {MIN_SPEECH_VOLUME}]")
                    result_text = ""
                else:
                    result_text = transcribe()

                print("\nTRANSCRIPTION:")
                print(result_text if result_text else "[Silence / Ignored]")

                if result_text:
                    print(f" -> Sending via Webhook: '{result_text}'")
                    payload = {
                        "channel": "Voice",
                        "text": result_text
                    }
                    try:
                        web_response = requests.post(WEBHOOK_URL, json=payload, timeout=60)
                        if web_response.status_code == 200:
                            ai_reply = web_response.json().get("reply", "").strip()
                            if ai_reply:
                                speak(ai_reply)
                        else:
                            print(f"\n[Error] Webhook responded with status code: {web_response.status_code}")
                    except Exception as e:
                        print(f"\n[Error] Failed executing webhook message exchange: {e}")

                # --- COOLDOWN BEFORE RE-LISTENING ---
                # Gives the mic/model time to settle so the same wake word audio
                # tail doesn't immediately re-trigger detection.
                time.sleep(1.0)
                print("\n--- Listening again ---\n")

                # Reset openWakeWord's internal prediction buffer so stale
                # confidence scores from before don't carry over.
                try:
                    oww_model.reset()
                except Exception:
                    pass

                # --- FLUSH AUDIO BUFFER BEFORE RE-OPENING ---
                det_stream = open_detection_stream()
                # Read out any audio data built up during transcription to throw it away
                try:
                    if det_stream.get_read_available() > 0:
                        det_stream.read(det_stream.get_read_available(), exception_on_overflow=False)
                except Exception:
                    pass

    except KeyboardInterrupt:
        print("\nExit requested by user.")
    finally:
        try:
            det_stream.stop_stream()
            det_stream.close()
        except Exception:
            pass
        pa.terminate()

if __name__ == "__main__":
    main()