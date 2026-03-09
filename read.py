import os
import re
import yaml
import google.generativeai as genai
from dotenv import load_dotenv
from notion_ops import create_review_page, mark_page_done
from drive_ops import upload_to_drive

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

DRIVE_READ_FOLDER_ID = os.getenv('DRIVE_READ_FOLDER_ID')

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_infra():
    with open("infrastructure.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def extract_title(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines:
        if line.startswith("CHAPTER TITLE:"):
            title = line.replace("CHAPTER TITLE:", "").strip()
            if len(title) > 65:
                title = title[:62] + "..."
            return title
    if lines:
        title = lines[0].replace('*', '').replace('#', '').strip()
        if len(title) > 65:
            title = title[:62] + "..."
        return title
    return "Untitled Chapter"

def run_reading_deep_dive(topic_title, page_id=None):
    topic_title = topic_title.strip()
    print(f"📚 Read Bot started for: {topic_title}")
    config = load_config()
    infra = load_infra()

    # --- DYNAMIC PATH INJECTION ---
    local_storage_path = infra['directories']['reading']
    os.makedirs(local_storage_path, exist_ok=True)
    
    safe_uid = re.sub(r'[\\/*?:"<>|]', "", topic_title)
    safe_uid = safe_uid.replace(' ', '_').replace('\n', '').replace('\r', '').strip()
    
    txt_filename = f"{safe_uid}.txt"
    local_txt_path = os.path.join(local_storage_path, txt_filename)

    model = genai.GenerativeModel(config.get('gemini_model', 'gemini-2.0-flash'))
    chat = model.start_chat(history=[]) 
    
    full_script = ""
    toc_lines = []

    print("... Writing Chapter 1 (Intro)")
    response = chat.send_message(config['read_prompt'].format(topic=topic_title))
    
    ch1_title = extract_title(response.text)
    toc_lines.append(f"Chapter 1: {ch1_title}")
    full_script += f"CHAPTER 1: INTRO\n\n{response.text}\n\n------------------------\n\n"

    loop_count = config.get('read_loop_count', 15)
    for i in range(loop_count):
        print(f"... Writing Chapter {i+2}/{loop_count + 1}")
        response = chat.send_message(config['read_loop_prompt'])
        ch_title = extract_title(response.text)
        toc_lines.append(f"Chapter {i+2}: {ch_title}")
        full_script += f"CHAPTER {i+2}: DEEP DIVE\n\n{response.text}\n\n------------------------\n\n"

    print("... Compiling Table of Contents")
    toc_header = "TABLE OF CONTENTS\n" + "="*40 + "\n"
    for line in toc_lines:
        toc_header += f"{line}\n"
    toc_header += "="*40 + "\n\n\n"

    final_document = toc_header + full_script

    with open(local_txt_path, "w", encoding="utf-8") as f:
        f.write(final_document)

    if DRIVE_READ_FOLDER_ID:
        print(f"☁️ Uploading {txt_filename} to Google Drive...")
        upload_to_drive(local_txt_path, txt_filename, DRIVE_READ_FOLDER_ID, 'text/plain')
    else:
        print("⚠️ DRIVE_READ_FOLDER_ID not found in .env. Skipping Drive upload.")

    print("... Generating Review Page")
    create_review_page(topic_title, safe_uid, db_type="read")
    
    if page_id:
        mark_page_done(page_id)

    print(f"🎉 Success! Read deep dive saved and uploaded.")