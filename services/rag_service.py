import chromadb
import google.generativeai as genai
import logging
import config

logger = logging.getLogger("DonaldBot")

class RagService:
    def __init__(self):
        self.chroma_client = None
        self.toybox_collection = None
        
        # Configure Gemini API for embeddings
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
            logger.info("✅ Gemini API configured for RAG service.")
        else:
            logger.warning("⚠️ GEMINI_API_KEY not found. Embedding features will fail.")
        
        self.setup_chromadb()

    def setup_chromadb(self):
        try:
            self.chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
            self.toybox_collection = self.chroma_client.get_or_create_collection(name="toybox_collection")
            logger.info(f"✅ ChromaDB connected. Collection has {self.toybox_collection.count()} items.")
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB: {e}")
            self.toybox_collection = None

    async def retrieve_toyboxes(self, query: str, max_results: int = 15) -> list[dict]:
        """Finds relevant toyboxes using fast vector search."""
        if not self.toybox_collection:
            logger.error("❌ Vector DB not available, cannot retrieve.")
            return []

        logger.info(f"--- Performing vector search for query: '{query}' ---")
        try:
            # 1. Create an embedding for the user's query
            query_embedding = genai.embed_content(
                model=config.EMBEDDING_MODEL_NAME,
                content=query,
                task_type="retrieval_query"
            )['embedding']

            # 2. Query ChromaDB for the most similar documents
            results = self.toybox_collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results
            )

            # 3. Format the results
            found_toyboxes = []
            if results and results['ids'][0]:
                for i, toybox_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i]
                    found_toyboxes.append({
                        "id": toybox_id,
                        "name": metadata.get("name", "Unknown"),
                        "url": metadata.get("url", ""),
                        "description": results['documents'][0][i], 
                        "tags": metadata.get("tags", "").split(",")
                    })
            
            logger.info(f"   -> Found {len(found_toyboxes)} relevant results from vector search.")
            return found_toyboxes

        except Exception as e:
            logger.error(f"❌ Error during vector retrieval: {e}")
            return []

    async def search_by_category(self, category: str, limit: int = 25) -> list[dict]:
        """Finds toyboxes with a specific tag."""
        if not self.toybox_collection:
            return []
            
        try:
            results = self.toybox_collection.get(
                where={"tags": {"$contains": category}},
                limit=limit
            )
            
            found_toyboxes = []
            if results and results['ids']:
                for i, toybox_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    found_toyboxes.append({
                        "name": metadata.get("name", "Unknown"),
                        "url": metadata.get("url", ""),
                        "tags": metadata.get("tags", "").split(","),
                        "category": category
                    })
            return found_toyboxes
            return found_toyboxes
        except Exception as e:
            logger.error(f"Error searching category {category}: {e}")
            return []

    async def ingest_new_data(self, toybox_list: list[dict]):
        """Ingests new toyboxes into the vector database."""
        if not self.toybox_collection:
            logger.warning("⚠️ Vector DB not available, skipping ingestion.")
            return

        logger.info(f"🔄 Check for new toyboxes to ingest ({len(toybox_list)} items)...")
        
        # Get existing IDs to avoid re-embedding
        existing_ids = self.toybox_collection.get()['ids']
        
        new_items = []
        new_ids = []
        new_metadatas = []
        new_documents = []

        for tb in toybox_list:
            str_id = str(tb['id'])
            if str_id not in existing_ids:
                # Prepare data for insertion
                # text_content combining name, description and tags for better embedding
                text_content = f"{tb['name']}\n{tb['description']}\nTags: {', '.join(tb['tags'])}"
                
                new_ids.append(str_id)
                new_documents.append(text_content)
                new_metadatas.append({
                    "name": tb['name'],
                    "url": tb['url'],
                    "tags": ",".join(tb['tags'])
                })
        
        if not new_ids:
            logger.info("✅ Vector DB is up to date.")
            return

        logger.info(f"🔄 Ingesting {len(new_ids)} new toyboxes into Vector DB...")
        
        try:
             # Generate embeddings in batches if needed, but ChromaDB might handle it or we use Gemini explicitly
             # Since we configured Gemini in __init__, we need to generate embeddings manually if we don't use an embedding function
             # The existing retrieve_toyboxes uses genai.embed_content explicitly.
             # So we should probably do the same here or rely on a default if one was set.
             # Looking at __init__, no embedding function was passed to get_or_create_collection.
             # So we must generate embeddings.
             
            embeddings = []
            # Batch size for embeddings to avoid rate limits
            BATCH_SIZE = 10
            for i in range(0, len(new_documents), BATCH_SIZE):
                batch_docs = new_documents[i:i+BATCH_SIZE]
                
                # Gemini embed_content supports batching? 
                # According to docs: yes, but let's be safe and loop or check support.
                # Actually, standard genai.embed_content takes 'content' (str) or 'content' (list)?
                # To be safe and consistent with retrieve_toyboxes, let's just loop for now or use the batch method if available.
                # Simple loop for safety:
                for doc in batch_docs:
                    emb = genai.embed_content(
                        model=config.EMBEDDING_MODEL_NAME,
                        content=doc,
                        task_type="retrieval_document"
                    )['embedding']
                    embeddings.append(emb)

            self.toybox_collection.add(
                ids=new_ids,
                documents=new_documents,
                embeddings=embeddings,
                metadatas=new_metadatas
            )
            logger.info(f"✅ Successfully added {len(new_ids)} new items to Vector DB.")
            
        except Exception as e:
            logger.error(f"❌ Error ingesting data into Vector DB: {e}")


# Global instance
rag_service = RagService()
