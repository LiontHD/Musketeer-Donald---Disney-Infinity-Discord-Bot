import chromadb
import json
import os

# --- CONFIGURATION ---
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "toybox_collection"
BLACKLIST_FILE = "blacklisted_threads.json"
TOYBOX_DATA_FILE = "toybox_data.json"

def main():
    print("--- Starting ChromaDB and JSON Cleanup ---")

    # 1. Load the blacklist
    print(f"Loading blacklist from {BLACKLIST_FILE}...")
    try:
        with open(BLACKLIST_FILE, 'r') as f:
            blacklisted_ids = json.load(f)
        if not blacklisted_ids:
            print("Blacklist is empty. Nothing to do.")
            return
        print(f"   -> Found {len(blacklisted_ids)} blacklisted thread IDs to remove.")
    except FileNotFoundError:
        print(f"❌ Error: '{BLACKLIST_FILE}' not found. Cannot proceed.")
        return

    # 2. Connect to ChromaDB
    print(f"\nConnecting to ChromaDB at '{CHROMA_DB_PATH}'...")
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        print(f"   -> Successfully connected to collection '{COLLECTION_NAME}'.")
        print(f"   -> Items in DB before cleaning: {collection.count()}")
    except Exception as e:
        print(f"❌ Error connecting to ChromaDB: {e}")
        return

    # 3. Delete items from ChromaDB
    print("\nRemoving blacklisted IDs from the vector database...")
    try:
        collection.delete(ids=blacklisted_ids)
        print("   -> Deletion command executed successfully.")
        print(f"   -> Items in DB after cleaning: {collection.count()}")
    except Exception as e:
        print(f"   -> ⚠️ Warning: An error occurred during deletion: {e}")


    # 4. Clean up toybox_data.json for consistency
    print(f"\nCleaning up '{TOYBOX_DATA_FILE}'...")
    try:
        with open(TOYBOX_DATA_FILE, 'r', encoding='utf-8') as f:
            all_toyboxes = json.load(f)
        
        original_count = len(all_toyboxes)
        # Create a new list containing only the items NOT in the blacklist
        cleaned_toyboxes = [tb for tb in all_toyboxes if str(tb.get('id')) not in blacklisted_ids]
        cleaned_count = len(cleaned_toyboxes)

        if original_count == cleaned_count:
            print("   -> No blacklisted items found in the JSON file. It's already clean.")
        else:
            with open(TOYBOX_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(cleaned_toyboxes, f, indent=4, ensure_ascii=False)
            print(f"   -> Removed {original_count - cleaned_count} items from the JSON file.")
            print(f"   -> Total items in JSON now: {cleaned_count}")

    except FileNotFoundError:
        print(f"   -> ⚠️ Warning: '{TOYBOX_DATA_FILE}' not found. Skipping JSON cleanup.")
    except Exception as e:
        print(f"   -> ❌ Error cleaning JSON file: {e}")

    print("\n✅ Cleanup complete!")

if __name__ == "__main__":
    main()