import pytest
import discord
from discord.ext import commands
from unittest.mock import MagicMock, AsyncMock, patch
import json
import os
import sys
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs.daily_toybox import DailyToybox, DAILY_SUBSCRIBER_ROLE_ID
import config

@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=commands.Bot)
    bot.fetch_user = AsyncMock()
    bot.guilds = []
    return bot

@pytest.fixture
def cog(mock_bot):
    cog = DailyToybox(mock_bot)
    yield cog

@pytest.mark.asyncio
async def test_on_member_update_welcome(cog):
    # Setup mocks
    before = MagicMock(spec=discord.Member)
    after = MagicMock(spec=discord.Member)
    role = MagicMock(spec=discord.Role)
    role.id = DAILY_SUBSCRIBER_ROLE_ID
    
    after.guild.get_role.return_value = role
    
    # Simulate role addition
    before.roles = []
    after.roles = [role]
    after.send = AsyncMock()

    await cog.on_member_update(before, after)

    # Verify welcome DM sent
    after.send.assert_called()
    call_args = after.send.call_args
    
    embed = None
    if call_args.args:
        embed = call_args.args[0]
    elif 'embed' in call_args.kwargs:
        embed = call_args.kwargs['embed']
        
    assert embed is not None
    assert "Welcome to the Daily Toybox" in embed.title

@pytest.mark.asyncio
async def test_daily_task_role_based(cog, mock_bot):
    # Setup mocks
    guild = MagicMock(spec=discord.Guild)
    role = MagicMock(spec=discord.Role)
    role.id = DAILY_SUBSCRIBER_ROLE_ID
    
    member = MagicMock(spec=discord.Member)
    member.bot = False
    member.send = AsyncMock()
    
    role.members = [member]
    guild.get_role.return_value = role
    mock_bot.guilds = [guild]

    # Mock toybox data
    mock_toyboxes = [{"name": "Test Toybox", "description": "Desc", "url": "http://example.com"}]
    
    with patch('os.path.exists', return_value=True):
        with patch('json.load', return_value=mock_toyboxes):
             await cog.daily_task()

    # Verify DM sent to member
    member.send.assert_called()
    call_args = member.send.call_args
    
    embed = None
    if call_args.args:
        embed = call_args.args[0]
    elif 'embed' in call_args.kwargs:
        embed = call_args.kwargs['embed']
        
    assert embed is not None
    assert "Toybox of the Day" in embed.title

if __name__ == "__main__":
    async def run_tests():
        print("Running manual tests (Role-Based)...")
        
        mock_bot_inst = MagicMock(spec=commands.Bot)
        cog_inst = DailyToybox(mock_bot_inst)
            
        try:
            print("Testing welcome message...")
            await test_on_member_update_welcome(cog_inst)
            print("✅ Welcome message passed")
            
            print("Testing daily task...")
            await test_daily_task_role_based(cog_inst, mock_bot_inst)
            print("✅ Daily task passed")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
                
    asyncio.run(run_tests())
