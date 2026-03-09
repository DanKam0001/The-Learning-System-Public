import os
import torch
import uuid
from TTS.api import TTS
from pydub import AudioSegment

# --- CONFIGURATION ---
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"🔈 Initializing Coqui TTS on {device}...")
try:
    tts = TTS(MODEL_NAME).to(device)
except Exception as e:
    print(f"❌ Error loading TTS model: {e}")
    tts = None

def generate_local_audio(text, output_path, ref_voice_path="reference.wav"):
    """
    Generates audio using Coqui XTTS locally.
    Groups short paragraphs into optimal ~1200 character blocks for maximum natural flow 
    and VRAM safety, relying on XTTS internal sentence splitting.
    """
    
    if not tts:
        print("❌ TTS Model not loaded. Skipping audio.")
        return

    if not os.path.exists(ref_voice_path):
        print(f"❌ Error: '{ref_voice_path}' not found! Please add it to your folder.")
        return

    # 1. Smart Block Chunking
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    
    MAX_CHAR_LIMIT = 1200  # The sweet spot for 6GB VRAM and XTTS context
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # If adding the next paragraph pushes us over the 1200 limit, save the current chunk and start a new one
        if len(current_chunk) + len(para) > MAX_CHAR_LIMIT and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
        else:
            current_chunk += para + "\n\n"
            
    # Catch any leftover text
    if current_chunk:
        chunks.append(current_chunk.strip())

    print(f"   🎙️  Processing {len(chunks)} optimized text blocks locally...")
    
    combined_audio = AudioSegment.empty()
    temp_chunk_path = f"temp_chunk_{uuid.uuid4().hex}.wav"

    # 2. Process Blocks
    for i, chunk in enumerate(chunks):
        try:
            tts.tts_to_file(
                text=chunk, 
                file_path=temp_chunk_path,
                speaker_wav=ref_voice_path,
                language="en",
                split_sentences=True  # Lets Coqui naturally handle the pacing inside the 1200-char block
            )
            
            segment = AudioSegment.from_wav(temp_chunk_path)
            combined_audio += segment
            
            # The 450ms pause now only happens between major 1200-character thematic blocks
            combined_audio += AudioSegment.silent(duration=450)
            
            print(f"      - Block {i+1}/{len(chunks)} encoded.")
            
        except Exception as e:
            print(f"❌ Error on block {i+1}: {e}")

    # 3. Export Final File
    combined_audio.export(output_path, format="mp3", bitrate="192k")
    
    # 4. Cleanup temporary file
    if os.path.exists(temp_chunk_path):
        os.remove(temp_chunk_path)

    print(f"✅ Natural Audio Saved: {output_path}")