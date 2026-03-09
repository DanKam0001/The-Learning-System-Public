import os
import re
import yaml
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()
notion = Client(auth=os.getenv('NOTION_TOKEN'), notion_version="2022-06-28")

GLOSSARY_DB_ID = os.getenv('GLOSSARY_DB_ID')
REVIEW_LEARN_DB_ID = os.getenv('REVIEW_LEARN_DB_ID') 
REVIEW_AUDIO_DB_ID = os.getenv('REVIEW_AUDIO_DB_ID') 
REVIEW_READ_DB_ID = os.getenv('REVIEW_READ_DB_ID')   

# --- NEW: LOAD INFRASTRUCTURE ---
def load_infra():
    with open("infrastructure.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

infra = load_infra()
CACHE_FILE = infra['system_files']['glossary_cache']

# --- HELPER: CACHE MANAGEMENT ---
def load_local_cache():
    if not os.path.exists(CACHE_FILE):
        return set()
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip().lower() for line in f)

def append_to_cache(term):
    os.makedirs(infra['directories']['base_data_dir'], exist_ok=True)
    with open(CACHE_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{term.strip().lower()}\n")

# --- CORE PAGE FUNCTIONS (Raw API Versions) ---
def fetch_page_title(page_id):
    try:
        page = notion.request(path=f"pages/{page_id}", method="GET")
        if "Name" in page["properties"]:
            title_list = page["properties"]["Name"]["title"]
            if title_list:
                return title_list[0]["plain_text"]
        return "Untitled Page"
    except Exception as e:
        print(f"❌ Error fetching title: {e}")
        return None

def fetch_full_page_text(page_id):
    full_text = ""
    has_more = True
    next_cursor = None
    
    while has_more:
        try:
            query_params = {}
            if next_cursor: query_params["start_cursor"] = next_cursor
            
            res = notion.request(
                path=f"blocks/{page_id}/children", 
                method="GET", 
                query=query_params
            )
            
            for block in res.get('results', []):
                b_type = block['type']
                if 'rich_text' in block.get(b_type, {}):
                    content = "".join([t['plain_text'] for t in block[b_type]['rich_text']])
                    if content:
                        full_text += content + "\n"
            
            has_more = res.get('has_more', False)
            next_cursor = res.get('next_cursor', None)
        except Exception as e:
            print(f"❌ Error fetching blocks: {e}")
            break
            
    return full_text

def get_page_data(page_id):
    safe_uid = "unknown"
    try:
        page = notion.request(path=f"pages/{page_id}", method="GET")
        props = page.get('properties', {})
        
        if "Original ID" in props and props["Original ID"]["rich_text"]:
            safe_uid = props["Original ID"]["rich_text"][0]["plain_text"].strip()
            
        elif "Name" in props and props["Name"]["title"]:
            title = props["Name"]["title"][0]["plain_text"]
            safe_uid = re.sub(r'[\\/*?:"<>|]', "", title)
            safe_uid = safe_uid.replace(' ', '_').replace('\n', '').replace('\r', '').strip()
            
    except Exception as e:
        print(f"❌ Error fetching page data: {e}")
        
    content = fetch_full_page_text(page_id)
    return safe_uid, content

# --- GLOSSARY FUNCTIONS ---
def fetch_glossary_content(page_id):
    data = {"term": "", "definition": "", "origin": "N/A", "synonyms": "N/A", "examples": "N/A", "tag": "CONCEPT"}
    try:
        page = notion.request(path=f"pages/{page_id}", method="GET")
        
        props = page['properties']
        if "Term" in props:
            t_list = props["Term"]["title"]
            if t_list: data["term"] = t_list[0]["plain_text"]
        elif "Name" in props:
            t_list = props["Name"]["title"]
            if t_list: data["term"] = t_list[0]["plain_text"]
            
        if "Type" in props and props["Type"]["select"]:
            data["tag"] = props["Type"]["select"]["name"]
        elif "Select" in props and props["Select"]["select"]:
            data["tag"] = props["Select"]["select"]["name"]
        
        full_text = fetch_full_page_text(page_id)
        lines = full_text.split('\n')
        for line in lines:
            if "Definition:" in line: data["definition"] = line.replace("Definition:", "").strip()
            elif "Origin:" in line: data["origin"] = line.replace("Origin:", "").strip()
            elif "Synonyms:" in line: data["synonyms"] = line.replace("Synonyms:", "").strip()
            elif "Examples:" in line: data["examples"] = line.replace("Examples:", "").strip()
            
        return data
    except Exception as e:
        print(f"❌ Error fetching glossary content: {e}")
        return data

def mark_glossary_complete(page_id):
    try:
        notion.request(
            path=f"pages/{page_id}", 
            method="PATCH", 
            body={"properties": {"Status": {"status": {"name": "Done"}}}}
        )
        print(f"✅ Marked Glossary Item {page_id} as Done.")
    except Exception as e: print(f"❌ Error marking glossary done: {e}")

def add_glossary_term_to_db(term, definition, type_tag, origin, synonyms, examples):
    if not GLOSSARY_DB_ID: return

    cache = load_local_cache()
    if term.lower().strip() in cache:
        print(f"⚡ Skipping Duplicate Term: {term}")
        return

    safe_definition = definition if definition else "Definition not provided."
    safe_type = type_tag if type_tag else "Concept"
    safe_origin = origin if origin else "N/A"
    safe_synonyms = synonyms if synonyms else "N/A"
    safe_examples = examples if examples else "N/A"

    properties = {
        "Name": {"title": [{"text": {"content": term[:2000]}}]},
        "Select": {"select": {"name": safe_type}}
    }
    
    children = [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Definition: {safe_definition}"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Origin: {safe_origin}"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Synonyms: {safe_synonyms}"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Examples: {safe_examples}"}}]}}
    ]
    
    try:
        notion.request(
            path="pages", 
            method="POST", 
            body={
                "parent": {"database_id": GLOSSARY_DB_ID}, 
                "properties": properties,
                "children": children
            }
        )
        print(f"✅ Added to Glossary: {term}")
        append_to_cache(term)
    except Exception as e:
        print(f"❌ Failed to add glossary term '{term}': {e}")

# --- REVIEW/LEARN FUNCTIONS ---
def push_feedback_to_notion(page_id, feedback_data, glossary_data):
    print(f"📝 Pushing feedback to Notion Page {page_id}...")
    
    feedback_text = feedback_data.get('feedback', 'No specific corrections.')
    score_text = feedback_data.get('scores', 'N/A')
    analogy_text = feedback_data.get('memorization', '')
    
    feedback_chunks = [feedback_text[i:i+1950] for i in range(0, len(feedback_text), 1950)]
    rich_text_array = [{"type": "text", "text": {"content": chunk}} for chunk in feedback_chunks]
    
    analogy_chunks = [analogy_text[i:i+1950] for i in range(0, len(analogy_text), 1950)]
    if not analogy_chunks: analogy_chunks = ["N/A"]
    analogy_rich_text = [{"type": "text", "text": {"content": chunk}} for chunk in analogy_chunks]
    
    children = [
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "🎓 RUTHLESS FEEDBACK REPORT"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Scores: {score_text}"}}]}},
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Errors & Ghost Gaps"}}]}},
        {"object": "block", "type": "code", "code": {"rich_text": rich_text_array, "language": "markdown"}},
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Analogy Critique"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": analogy_rich_text}}
    ]
    
    try:
        notion.request(
            path=f"blocks/{page_id}/children", 
            method="PATCH", 
            body={"children": children}
        )
        print("✅ Feedback Report appended successfully.")
    except Exception as e:
        print(f"❌ Error appending feedback: {e}")

def create_review_page(topic_title, safe_uid, db_type="learn"):
    if db_type == "learn" or db_type == "audiobooks":     
        target_db = REVIEW_LEARN_DB_ID
    elif db_type == "audio":   
        target_db = REVIEW_AUDIO_DB_ID
    elif db_type == "read":    
        target_db = REVIEW_READ_DB_ID
    else:
        print(f"⚠️ Unknown db_type {db_type}. Skipping review page creation.")
        return None

    if not target_db: 
        print(f"⚠️ Missing Database ID for {db_type} in .env file.")
        return None

    try:
        response = notion.request(
            path="pages", 
            method="POST", 
            body={
                "parent": {"database_id": target_db},
                "properties": {
                    "Name": {"title": [{"text": {"content": topic_title}}]},
                    "Status": {"status": {"name": "Not started"}},
                    "Original ID": {"rich_text": [{"text": {"content": safe_uid}}]}
                }
            }
        )
        new_id = response.get('id')
        print(f"✅ Created Review Page: https://notion.so/{new_id.replace('-', '')}")
        return new_id
    except Exception as e:
        print(f"❌ Failed to create review page: {e}")
        return None

def mark_page_done(page_id):
    try:
        notion.request(
            path=f"pages/{page_id}", 
            method="PATCH", 
            body={"properties": {"Status": {"status": {"name": "Done"}}}}
        )
        print(f"✅ Marked page {page_id} as Done.")
    except Exception as e:
        print(f"❌ Error marking done: {e}")