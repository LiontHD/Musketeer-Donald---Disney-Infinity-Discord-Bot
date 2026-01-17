import discord
import json
import asyncio
import config
from services.tag_analyzer import SimpleTagAnalyzer
from services.rag_service import rag_service
from utils.logger import logger

class ToyboxService:
    async def update_toybox_database(self, guild: discord.Guild):
        forum_channel = guild.get_channel(config.FORUM_CHANNEL_ID)
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            logger.warning("⚠️ Forum channel not found!")
            return

        # Load existing data
        existing_toyboxes = {}
        try:
            with open(config.TOYBOX_DATA_FILE, "r", encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_toyboxes = {str(item['id']): item for item in existing_data}
        except FileNotFoundError:
            logger.info("📝 No existing toybox data found, creating new database...")

        analyzer = SimpleTagAnalyzer()
        toybox_list = []
        
        # Gather all threads
        threads = list(forum_channel.threads)
        async for archived_thread in forum_channel.archived_threads(limit=None):
            threads.append(archived_thread)
        
        logger.info(f"🔄 Updating Toybox database with {len(threads)} threads...")
        
        for thread in threads:
            thread_id = str(thread.id)
            
            # If thread exists and already has tags, preserve them
            if thread_id in existing_toyboxes:
                toybox_entry = existing_toyboxes[thread_id]
            else:
                # Only analyze new threads or threads without tags
                first_message = None
                async for msg in thread.history(oldest_first=True, limit=1):
                    first_message = msg
                    break

                if not first_message:
                    continue

                analysis_text = f"{thread.name} {first_message.content}"
                tags = analyzer.analyze_text(analysis_text)

                toybox_entry = {
                    "id": thread.id,
                    "name": thread.name,
                    "url": thread.jump_url,
                    "tags": tags,
                    "description": first_message.content
                }
            
            toybox_list.append(toybox_entry)

        # Save updated database
        with open(config.TOYBOX_DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(toybox_list, f, indent=4, ensure_ascii=False)
        
        
        logger.info(f"✅ Toybox database update complete. ({len(toybox_list)} entries processed).")
        
        # Sync with Vector DB
        ingested_count = await rag_service.ingest_new_data(toybox_list)
        
        return len(toybox_list), ingested_count

toybox_service = ToyboxService()
