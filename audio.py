import os
import re
import yaml
from dotenv import load_dotenv
from notion_ops import fetch_full_page_text, create_review_page, mark_page_done
from drive_ops import upload_to_drive
from local_tts import generate_local_audio

load_dotenv()

def load_infra():
    with open("infrastructure.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_audio_processing(page_id, title):
    title = title.strip()
    print(f"🎤 Audio Bot started for: {title}")
    
    infra = load_infra()
    raw_text = fetch_full_page_text(page_id)
    
    local_storage_path = infra['directories']['audio_notes']
    ref_voice_path = infra['system_files']['reference_voice']
    os.makedirs(local_storage_path, exist_ok=True)
    
    # --- BULLETPROOF FILENAME SANITIZATION ---
    safe_uid = re.sub(r'[\\/*?:"<>|]', "", title)
    safe_uid = safe_uid.replace(' ', '_').replace('\n', '').replace('\r', '').strip()
    
    txt_filename = f"{safe_uid}.txt"
    mp3_filename = f"{safe_uid}.mp3"
    local_txt_path = os.path.join(local_storage_path, txt_filename)
    local_mp3_path = os.path.join(local_storage_path, mp3_filename)
    
    with open(local_txt_path, "w", encoding="utf-8") as f:
        f.write(raw_text)

    print("... Generating Local Audio (Coqui)")
    generate_local_audio(
        text=raw_text,
        output_path=local_mp3_path,
        ref_voice_path=ref_voice_path
    )

    drive_id = os.getenv('DRIVE_AUDIO_FOLDER_ID')
    if drive_id:
        upload_to_drive(local_txt_path, txt_filename, drive_id, 'text/plain')
        upload_to_drive(local_mp3_path, mp3_filename, drive_id, 'audio/mpeg')

    create_review_page(title, safe_uid, db_type="audio")
    mark_page_done(page_id)