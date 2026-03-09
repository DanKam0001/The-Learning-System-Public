import threading
from flask import Flask, request, jsonify
from learn import run_deep_dive
from audio import run_audio_processing
from review import run_review_grading
from slide_generator import create_slide
from notion_ops import fetch_glossary_content, mark_glossary_complete, fetch_page_title
from read import run_reading_deep_dive

app = Flask(__name__)
MAX_CONCURRENT_JOBS = 1  # 🔥 STRICT SINGLE-THREAD QUEUE
job_lock = threading.Semaphore(MAX_CONCURRENT_JOBS)

def run_safe_worker(target_func, *args):
    with job_lock:
        print(f"🚦 Worker started. (Active jobs: 1, Queued: {threading.active_count() - 2})")
        target_func(*args)
    print("🏁 Worker finished.")

def extract_notion_title(data):
    try:
        page_id = data.get('data', {}).get('id')
        if 'data' in data and 'properties' in data['data'] and 'Name' in data['data']['properties']:
             return data['data']['properties']['Name']['title'][0]['text']['content']
        if page_id: return fetch_page_title(page_id)
        return "Untitled"
    except: return "Untitled"

@app.route('/learn', methods=['POST'])
def learn_endpoint():
    data = request.json
    title = extract_notion_title(data)
    page_id = data.get('data', {}).get('id')
    threading.Thread(target=run_safe_worker, args=(run_deep_dive, title, page_id)).start()
    return jsonify({"status": "Job Queued"}), 200

@app.route('/audio', methods=['POST'])
def audio_endpoint():
    data = request.json
    title = extract_notion_title(data)
    page_id = data.get('data', {}).get('id')
    threading.Thread(target=run_safe_worker, args=(run_audio_processing, page_id, title)).start()
    return jsonify({"status": "Job Queued"}), 200

@app.route('/read', methods=['POST'])
def read_endpoint():
    data = request.json
    title = extract_notion_title(data)
    page_id = data.get('data', {}).get('id')
    threading.Thread(target=run_safe_worker, args=(run_reading_deep_dive, title, page_id)).start()
    return jsonify({"status": "Job Queued"}), 200

@app.route('/review', methods=['POST'])
def review_endpoint():
    page_id = request.json.get('data', {}).get('id')
    threading.Thread(target=run_safe_worker, args=(run_review_grading, page_id, "learn")).start()
    return jsonify({"status": "Review Queued"}), 200

@app.route('/review_audio', methods=['POST'])
def review_audio_endpoint():
    page_id = request.json.get('data', {}).get('id')
    threading.Thread(target=run_safe_worker, args=(run_review_grading, page_id, "audio")).start()
    return jsonify({"status": "Review Queued"}), 200

@app.route('/review_read', methods=['POST'])
def review_read_endpoint():
    page_id = request.json.get('data', {}).get('id')
    threading.Thread(target=run_safe_worker, args=(run_review_grading, page_id, "read")).start()
    return jsonify({"status": "Review Queued"}), 200

@app.route('/glossary', methods=['POST'])
def glossary_endpoint():
    data = request.json
    page_id = data.get('data', {}).get('id')
    term = extract_notion_title(data)
    
    def glossary_worker(pid, t):
        content = fetch_glossary_content(pid)
        create_slide(t, content.get('definition'), content.get('examples'), content.get('tag'), content.get('origin'), content.get('synonyms'))
        mark_glossary_complete(pid)
        
    threading.Thread(target=run_safe_worker, args=(glossary_worker, page_id, term)).start()
    return jsonify({"status": "Slide Queued"}), 200

if __name__ == '__main__':
    app.run(port=5000)