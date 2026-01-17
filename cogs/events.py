import discord
from discord.ext import commands
import asyncio
import time
import random
import traceback
import google.generativeai as genai
from services.rag_service import rag_service
from views.counting_views import CountingView
from utils.logger import logger
import config

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # --- Part 1: AI Chat Logic ---
        is_ai_chat_thread = (
            not message.author.bot and
            isinstance(message.channel, discord.Thread) and
            hasattr(message.channel, 'owner') and message.channel.owner == self.bot.user and
            message.channel.type == discord.ChannelType.private_thread and
            message.channel.name.startswith("Toybox Chat with")
        )

        if is_ai_chat_thread:
            original_query = message.content.strip()
            if not original_query or original_query.startswith(('/', '!', '$', '#')):
                return

            if not self.bot.gemini_model:
                await message.channel.send("❌ Waaak! My thinking cap isn't working right now (AI features disabled). Please contact an admin.")
                return

            # Check if RAG service is ready (assuming it is if initialized)
            # In OG.py it checked bot.toybox_collection. rag_service handles this internally.

            # --- User Feedback ---
            start_time = time.time()
            thinking_phrases = [
                f"Searching for **'{original_query}'**... Waaak, there are so many toyboxes here! Let me find the best ones...",
                f"Let's see what we've got for **'{original_query}'**... Scanning the whole library, this might take a second!",
                f"Oh boy, oh boy! A request for **'{original_query}'**! I'll dive right into the archives and see what I can dig up for you!",
                f"Putting on my thinking cap for **'{original_query}'**... There are hundreds of toyboxes... let me find the perfect match!"
            ]
            thinking_embed = discord.Embed(
                title="🦆 Donald is thinking...",
                description=random.choice(thinking_phrases),
                color=discord.Color.blue()
            ).set_thumbnail(url="https://i.gifer.com/ZZ5H.gif")
            thinking_message = await message.channel.send(embed=thinking_embed)
            
            try:
                # --- STEP 0: REFINE QUERY ---
                search_query = original_query
                try:
                    refinement_prompt = f"""
                    Extract the essential keywords from the following user request.
                    Focus on character names, game genres (like 'racing', 'combat'), or franchises (like 'Marvel').
                    Ignore conversational filler like "I want to play" or "can you find me".
                    Return ONLY the keywords, separated by a space.

                    User request: "{original_query}"
                    
                    Keywords:
                    """
                    refinement_response = await asyncio.to_thread(
                        self.bot.gemini_model.generate_content,
                        refinement_prompt,
                        generation_config=genai.types.GenerationConfig(temperature=0.0)
                    )
                    
                    search_query = original_query # Default fallback
                    if refinement_response and hasattr(refinement_response, 'parts') and refinement_response.parts:
                        try:
                            # Verify if there is text content before accessing
                            if refinement_response.text:
                                search_query = refinement_response.text.strip()
                                logger.info(f"Query Refinement: Original='{original_query}' -> Refined='{search_query}'")
                        except ValueError:
                             logger.warning(f"Query Refinement: Response blocked or invalid (Finish Reason: {refinement_response.candidates[0].finish_reason}). Using original query.")
                    else:
                        logger.info(f"Query Refinement: No valid text parts returned. Using original query.")

                except Exception as e:
                    logger.error(f"⚠️ Error during query refinement: {e}. Falling back to original query.")
                    search_query = original_query

                # --- STEP 1: RETRIEVE CONTEXT ---
                retrieved_toyboxes = await rag_service.retrieve_toyboxes(
                    search_query,
                    max_results=10
                )

                # --- STEP 2: HANDLE NO RESULTS ---
                if not retrieved_toyboxes:
                    elapsed_time = time.time() - start_time
                    no_results_embed = discord.Embed(
                        title="🤔 Hmm, Quackers!",
                        description=(
                            f"Waaak! I searched my entire collection for things related to '**{search_query}**' but couldn't find a good match. 🦆\n\n"
                            f"**Maybe try asking differently?**\n"
                            f"• Mention a character, a game type (like 'racing' or 'boss battle'), or a movie!"
                        ),
                        color=discord.Color.orange()
                    ).set_footer(text=f"Search took {elapsed_time:.2f} seconds.")
                    await thinking_message.edit(embed=no_results_embed)
                    return

                # --- STEP 3: BUILD CONTEXT & PROMPT ---
                context_str = "Found these potentially relevant Toyboxes:\n\n"
                for i, tb in enumerate(retrieved_toyboxes, 1):
                    context_str += f"--- Toybox {i} ---\nName: {tb['name']}\nDescription: {tb['description']}\nLink: <{tb['url']}>\n\n"

                prompt = f"""You are a specialized, friendly and helpful assistant for the Disney Infinity community Discord server. Your goal is to help users find Toyboxes shared in the forum based on their questions, using ONLY the provided context. Be conversational and enthusiastic!

**Background:**
- The user's original request was: "{original_query}"
- To focus the search, the key subjects identified from the request were: "{search_query}"
- "Provided Toybox Information" below contains search results based on the identified key subjects "{search_query}".

**Instructions:**
1. Identify the core **subject or topic** the user is asking about, considering both their original request ("{original_query}") and the extracted search terms ("{search_query}"). Let's call this the 'User Topic'.
2. Carefully examine **each** item in the "Provided Toybox Information".
3. For each Toybox, determine if it is **genuinely relevant** to the 'User Topic' (especially related to '{search_query}').
    - **High Relevance:** Name, tags, or description *directly* relate to the 'User Topic' or the search terms '{search_query}'.
    - **Consider Relevance:** Even if the title doesn't exactly match, it's relevant if its content (judging by name, tags, description preview) clearly relates to the 'User Topic'/{search_query}.
    - **Ignore if irrelevant:** Disregard Toyboxes that seem unrelated to the 'User Topic'/{search_query}, even if they appeared in the search results.
4. Formulate a helpful and conversational response based **only** on the relevant Toyboxen you identified:
    - **If relevant Toyboxen were found:**
        - Start with a positive confirmation related to the 'User Topic'/{search_query}. Examples: "Oh boy, oh boy! I found some Toyboxes about {search_query}!", "Waaak! Look what I dug up for '{search_query}':", "Quack-tastic! Check out these Toyboxes featuring {search_query}:".
        
        - Recommend **only** the Toyboxen you deemed relevant in step 3, up to a maximum of 10. Present them in order from **most relevant to least relevant**.
        
        - For each recommended Toybox:
            - Use the Toybox Name as a **Markdown H2 heading** (e.g., `## Stitch's Great Escape`).
            - On the **next line**, briefly explain *why it's relevant* to the 'User Topic' or '{search_query}', citing details from the context (e.g., "This one features Stitch himself!" or "This race track sounds perfect for what you asked!").
            - Immediately following, include the **Link** as a **Markdown bullet point**: `* [🔗 Link](<URL>)`
    - **If, after careful review, none of the PROVIDED Toyboxen seem relevant to the 'User Topic'/{search_query}:**
        - State clearly in that none of the specific options **I examined from the search results** seemed to fit '{search_query}'. Example: "Aw, phooey! I looked through the list for '{search_query}', but none of these seem quite right..."
        - Briefly explain *why* based on the topic (e.g., "...they were mostly about other characters!").
        - Encourage them to try different terms. Example: "Maybe try asking for something else?"
    - **Strictly adhere to the provided information.** Do not make up details or add closing remarks like "Let me know...".

**Provided Toybox Information (Context - Use ONLY This):**
{context_str}

**User's Original Question:** {original_query}
**(Search focused on:** {search_query}**)

**Your Answer (Respond following all instructions, focusing *only* on relevant items from the provided context):**
"""

                # --- STEP 4: GENERATE AND SEND RESPONSE ---
                response = await asyncio.to_thread(
                    self.bot.gemini_model.generate_content,
                    prompt,
                    generation_config=genai.types.GenerationConfig(temperature=0.5),
                    safety_settings=[
                       {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
                    ]
                )

                # Check if response was blocked or empty
                if not response or not hasattr(response, 'text'):
                    block_reason = "Unknown"
                    if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                        block_reason = str(getattr(response.prompt_feedback, "block_reason", "Unknown"))
                    await thinking_message.edit(embed=discord.Embed(
                        title="⚠️ Waaak!",
                        description=f"My response got filtered (Reason: `{block_reason}`). Could you ask differently? 🦆",
                        color=discord.Color.orange()
                    ))
                    return

                # Try to get the text, handle if it's empty
                try:
                    answer = response.text.strip()
                    if not answer:
                        await thinking_message.edit(embed=discord.Embed(
                            title="⚠️ Hmm...",
                            description="I couldn't generate a response. Please try rephrasing your question! 🦆",
                            color=discord.Color.orange()
                        ))
                        return
                except (AttributeError, ValueError) as e:
                    logger.error(f"Error accessing response.text: {e}")
                    await thinking_message.edit(embed=discord.Embed(
                        title="⚠️ Oops!",
                        description="Something went wrong generating my response. Please try again! 🦆",
                        color=discord.Color.orange()
                    ))
                    return

                elapsed_time = time.time() - start_time

                final_embed = discord.Embed(
                    title="🦆 Here's what I found!",
                    description=answer[:4096] if len(answer) <= 4096 else answer[:4093] + "...",
                    color=discord.Color.green()
                ).set_footer(text=f"Search completed in {elapsed_time:.2f} seconds.")

                await thinking_message.edit(embed=final_embed)

                if len(answer) > 4096:
                    remaining_text = "[...]\n" + answer[4096:]
                    MAX_MSG_LENGTH = 2000
                    remaining_chunks = [remaining_text[i:i+MAX_MSG_LENGTH] for i in range(0, len(remaining_text), MAX_MSG_LENGTH)]
                    for chunk in remaining_chunks:
                        await message.channel.send(chunk)
                        await asyncio.sleep(0.6)
            except Exception as e:
                logger.error(f"❌ Unexpected Error during RAG processing in thread {message.channel.id}:")
                traceback.print_exc()
                elapsed_time = time.time() - start_time
                error_embed = thinking_message.embeds[0] if thinking_message.embeds else None
                if error_embed:
                    error_embed.set_footer(text=f"Error after {elapsed_time:.2f} seconds.")
                await message.channel.send(f"🦆 Waaak! An unexpected error ({type(e).__name__}) happened. I've logged it. Please try again or tell an admin!")
            
            return

        # --- Part 2: Counting Logic ---
        if message.author.id in self.bot.counter.counting_sessions:
            processed_files = []
            for attachment in message.attachments:
                if attachment.filename.endswith('.zip'):
                    zip_data = await attachment.read()
                    count = self.bot.counter.count_srr_files(zip_data, attachment.filename)
                    
                    self.bot.counter.counting_sessions.setdefault(message.author.id, []).append((attachment.filename, count))
                    processed_files.append((attachment.filename, count))
            
            if processed_files:
                total = sum(count for _, count in self.bot.counter.counting_sessions[message.author.id])
                
                progress_embed = discord.Embed(
                    title="📊 Toybox Counting Session",
                    description="Upload ZIP files to count toyboxes.\nCurrent progress shown below.",
                    color=0xdb6534 # Orange
                )
                progress_embed.add_field(name="━━ File Details ━━", value="", inline=False)
                for fname, fcount in self.bot.counter.counting_sessions[message.author.id]:
                    formatted_filename = fname.replace('_', ' ').replace('.zip', '')
                    progress_embed.add_field(
                        name=f"📦 {formatted_filename}",
                        value=f"> Found `{fcount}` Toybox{'es' if fcount != 1 else ''}",
                        inline=False
                    )
                progress_embed.add_field(name="━━ Summary ━━", value="", inline=False)
                progress_embed.add_field(
                    name="📈 Current Total",
                    value=f"```\n{total} Toybox{'es' if total != 1 else ''}\n```",
                    inline=False
                )
                progress_embed.timestamp = discord.utils.utcnow()
                progress_embed.set_footer(
                    text="Toybox Count Bot | Session in Progress 🔄",
                    icon_url="https://cdn.discordapp.com/emojis/1039238467898613851.webp?size=96&quality=lossless"
                )
                
                progress_message_obj = self.bot.counter.progress_messages.get(message.author.id)
                if progress_message_obj:
                    await progress_message_obj.edit(embed=progress_embed, view=CountingView(self.bot.counter, message.author.id, progress_message_obj))
                
                if len(processed_files) == len(message.attachments):
                    try:
                        await message.delete()
                    except discord.HTTPException:
                        pass

        # --- Part 3: Process Commands ---
        await self.bot.process_commands(message)

async def setup(bot):
    await bot.add_cog(Events(bot))
