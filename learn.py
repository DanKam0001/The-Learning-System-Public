import os
import re
import yaml
import google.generativeai as genai
from dotenv import load_dotenv
from notion_ops import create_review_page, mark_page_done
from drive_ops import upload_to_drive
from local_tts import generate_local_audio

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_infra():
    with open("infrastructure.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_deep_dive(topic_title, page_id=None):
    topic_title = topic_title.strip()
    print(f"🚀 Learn Bot started for: {topic_title}")
    config = load_config()
    infra = load_infra()

    # --- DYNAMIC PATH INJECTION ---
    local_storage_path = infra['directories']['audiobooks']
    ref_voice_path = infra['system_files']['reference_voice']
    os.makedirs(local_storage_path, exist_ok=True)
    
    safe_uid = re.sub(r'[\\/*?:"<>|]', "", topic_title)
    safe_uid = safe_uid.replace(' ', '_').replace('\n', '').replace('\r', '').strip()
    
    txt_filename = f"{safe_uid}.txt"
    mp3_filename = f"{safe_uid}.mp3"
    local_txt_path = os.path.join(local_storage_path, txt_filename)
    local_mp3_path = os.path.join(local_storage_path, mp3_filename)

    model = genai.GenerativeModel(config.get('gemini_model', 'gemini-2.0-flash'))
    chat = model.start_chat(history=[]) 
    full_script = ""

    print("... Writing Intro")
    response = chat.send_message(config['learn_prompt'].format(topic=topic_title))
    full_script += f"{response.text}\n\n"

    for i in range(config.get('audio_loop_count', 3)):
        print(f"... Writing Loop {i+1}")
        response = chat.send_message(config['loop_prompt'])
        full_script += f"{response.text}\n\n"

    with open(local_txt_path, "w", encoding="utf-8") as f:
        f.write(full_script)

    print("... Generating Local Audio (Coqui)")
    generate_local_audio(
        text=full_script,
        output_path=local_mp3_path,
        ref_voice_path=ref_voice_path
    )

    drive_id = os.getenv('DRIVE_LEARN_FOLDER_ID')
    if drive_id:
        upload_to_drive(local_txt_path, txt_filename, drive_id, 'text/plain')
        upload_to_drive(local_mp3_path, mp3_filename, drive_id, 'audio/mpeg')

    create_review_page(topic_title, safe_uid, db_type="audiobooks")

    if page_id:
        mark_page_done(page_id)