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
        except Exception as e:
            logger.error(f"Error searching category {category}: {e}")
            return []

# Global instance
rag_service = RagService()
