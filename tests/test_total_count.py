import pytest
import discord
from discord.ext import commands
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs.admin import AdminCommands
import config

@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=commands.Bot)
    bot.counter = MagicMock()
    bot.counter.count_srr_files.return_value = 5 # Mock 5 toyboxes per zip
    return bot

@pytest.fixture
def cog(mock_bot):
    return AdminCommands(mock_bot)

@pytest.mark.asyncio
async def test_count_total_toyboxes_ascii_art(cog):
    # Setup mocks
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild.get_channel.return_value = MagicMock(spec=discord.ForumChannel)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    status_message = AsyncMock()
    interaction.followup.send.return_value = status_message
    
    # Mock thread
    thread1 = MagicMock(spec=discord.Thread)
    thread1.id = 1
    
    # Mock messages
    msg1 = MagicMock(spec=discord.Message)
    msg1.id = 101
    attachment = MagicMock(spec=discord.Attachment)
    attachment.filename = "test.zip"
    attachment.read = AsyncMock(return_value=b"fake_zip_data")
    msg1.attachments = [attachment]
    
    # Mock history iterator
    async def history_iterator(limit=None, oldest_first=True):
        yield msg1
    
    thread1.history = history_iterator
    
    # Setup forum channel threads
    forum_channel = interaction.guild.get_channel.return_value
    forum_channel.threads = [thread1]
    
    # Mock archived threads iterator (empty for this test)
    async def archived_threads_iterator(limit=None):
        if False: yield # Empty generator
    
    forum_channel.archived_threads = archived_threads_iterator

    # Run command
    await cog.count_total_toyboxes.callback(cog, interaction)

    # Verify results
    
    # Check final embed
    status_message.edit.assert_called()
    call_args = status_message.edit.call_args
    
    embed = None
    if call_args.args:
        embed = call_args.args[0]
    elif 'embed' in call_args.kwargs:
        embed = call_args.kwargs['embed']
        
    assert embed is not None
    assert "Toybox Count Complete" in embed.title
    
    # Verify total count field contains ASCII art (code block)
    found_count = False
    for field in embed.fields:
        if field.name == "Total Toyboxes":
            # Should contain code block markers
            assert "```" in field.value
            found_count = True
            break
    assert found_count

if __name__ == "__main__":
    async def run_tests():
        print("Running manual tests (Total Count - ASCII Art)...")
        
        mock_bot_inst = MagicMock(spec=commands.Bot)
        mock_bot_inst.counter = MagicMock()
        mock_bot_inst.counter.count_srr_files.return_value = 5
        
        cog_inst = AdminCommands(mock_bot_inst)
            
        try:
            print("Testing count_total_toyboxes ASCII output...")
            await test_count_total_toyboxes_ascii_art(cog_inst)
            print("✅ Count command passed (ASCII Art verified)")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
                
    asyncio.run(run_tests())
