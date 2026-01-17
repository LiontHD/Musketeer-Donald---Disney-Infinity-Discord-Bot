import google.generativeai as genai
import chromadb
import json
import os
import time
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
TOYBOX_DATA_FILE = "toybox_data.json"
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "toybox_collection"

# --- INITIALIZE AI & DB ---
print("Initializing Gemini and ChromaDB...")
try:
    genai.configure(api_key=GEMINI_API_KEY)
    tagging_model = genai.GenerativeModel('gemini-2.5-flash')
    embedding_model = 'models/embedding-001'
    
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    print("✅ Initialization complete.")
except Exception as e:
    print(f"❌ Failed to initialize: {e}")
    exit()

def get_ai_tags(toybox_name, toybox_desc):
    """Uses Gemini to generate descriptive gameplay tags for a toybox."""
    print(f"   -> Generating AI tags for '{toybox_name}'...")
    desc_snippet = (toybox_desc[:1500] + '...') if len(toybox_desc) > 1500 else toybox_desc
    
    prompt = f"""
    Analyze the following Disney Infinity Toybox information. Based on the title and description, identify its core gameplay mechanics and themes.
    Return a Python list of 2-5 descriptive string tags.

    Example tags: "Racing", "Platformer", "Combat Arena", "Boss Battle", "Maze", "Music", "Art", "Puzzle", "Story Driven", "Exploration", "Movie Recreation".
    Only include tags clearly supported by the text. If no specific mechanics are clear, return an empty list: [].

    Information:
    Title: "{toybox_name}"
    Description: "{desc_snippet}"
    ---
    Tags (Python list of strings):
    """
    
    try:
        response = tagging_model.generate_content(prompt)
        # <<< FIX: More robust cleaning logic for the AI's response
        clean_text = response.text.strip()
        # Remove markdown code blocks and brackets
        clean_text = clean_text.replace("```python", "").replace("```", "")
        clean_text = clean_text.replace("[", "").replace("]", "")
        clean_text = clean_text.replace("'", "").replace('"', "")
        
        if not clean_text:
            return []
        # Split by comma and strip whitespace from each tag
        ai_tags = [tag.strip() for tag in clean_text.split(',') if tag.strip()]
        return ai_tags
    except Exception as e:
        print(f"      ⚠️ AI Tagging Error: {e}")
        return []

def main():
    print(f"Loading toybox data from {TOYBOX_DATA_FILE}...")
    try:
        with open(TOYBOX_DATA_FILE, 'r', encoding='utf-8') as f:
            all_toyboxes = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: '{TOYBOX_DATA_FILE}' not found. Run the /update_toyboxes command first.")
        return
    
    print(f"Found {len(all_toyboxes)} toyboxes. Starting indexing process...")
    
    updated_toyboxes = []
    for i, toybox in enumerate(all_toyboxes):
        print(f"\n[{i+1}/{len(all_toyboxes)}] Processing Toybox ID: {toybox['id']}")
        toybox_id = str(toybox['id'])

        if len(collection.get(ids=[toybox_id])['ids']) > 0:
            print(f"   -> Already indexed. Skipping.")
            updated_toyboxes.append(toybox)
            continue

        description = toybox.get("description", "")
        ai_tags = get_ai_tags(toybox['name'], description)
        
        existing_tags = toybox.get("tags", [])
        combined_tags = list(set(existing_tags + ai_tags))
        toybox['tags'] = combined_tags
        print(f"   -> Combined Tags: {combined_tags}")

        document_text = (
            f"Name: {toybox['name']}. "
            f"Tags: {', '.join(combined_tags)}. "
            f"Description: {description}"
        )

        print("   -> Generating vector embedding...")
        embedding = genai.embed_content(
            model=embedding_model,
            content=document_text,
            task_type="retrieval_document"
        )['embedding']

        print("   -> Storing in ChromaDB...")
        collection.add(
            ids=[toybox_id],
            embeddings=[embedding],
            documents=[document_text],
            metadatas=[{"name": toybox['name'], "url": toybox['url'], "tags": ", ".join(combined_tags)}]
        )
        
        updated_toyboxes.append(toybox)
        
        time.sleep(1.1) 

    print("\nSaving enriched toybox data back to file...")
    with open(TOYBOX_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(updated_toyboxes, f, indent=4, ensure_ascii=False)
        
    print("✅ Indexing complete! The bot's brain is now up to date.")

if __name__ == "__main__":
    main()