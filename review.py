import os
import yaml
import json
import google.generativeai as genai
from dotenv import load_dotenv
from notion_ops import get_page_data, push_feedback_to_notion, add_glossary_term_to_db, mark_page_done

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def load_infra():
    with open("infrastructure.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_review_grading(page_id, mode="learn"):
    print(f"🧐 Review Bot ({mode.upper()}) started for Page ID: {page_id}")
    
    ext = ".txt"
    uid, user_notes = get_page_data(page_id)
    
    # --- DYNAMIC FOLDER SEARCH VIA INFRASTRUCTURE ---
    infra = load_infra()
    possible_folders = [
        infra['directories']['audiobooks'], 
        infra['directories']['legacy_learn'], 
        infra['directories']['audio_notes'], 
        infra['directories']['reading']
    ]
    
    original_path = None
    for folder in possible_folders:
        temp_path = os.path.join(folder, f"{uid}{ext}")
        if os.path.exists(temp_path):
            original_path = temp_path
            break
            
    if not original_path:
        print(f"❌ Error: Local hash file '{uid}{ext}' not found in any data folder.")
        return
        
    print(f"✅ Found original file at: {original_path}")

    with open(original_path, "r", encoding="utf-8") as f:
        original_text = f.read()

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    model = genai.GenerativeModel(config.get('gemini_model', 'gemini-2.0-flash'))
    prompt = config['review_prompt'].format(original_text=original_text, user_notes=user_notes)
    
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    
    try:
        data = json.loads(response.text)
        glossary_data = data.get("glossary", [])
        
        push_feedback_to_notion(page_id, data.get("feedback_report", {}), glossary_data)
        
        for item in glossary_data:
            add_glossary_term_to_db(
                term=item.get('term'), 
                definition=item.get('definition'),
                type_tag=item.get('type', 'Concept'),
                origin=item.get('origin', 'N/A'),
                synonyms=item.get('synonyms', 'N/A'),
                examples=item.get('examples', 'N/A')
            )
            
        mark_page_done(page_id)
        print("🎉 Review Complete. Glossary updated.")
        
    except Exception as e:
        print(f"❌ Error parsing or pushing review data: {e}")