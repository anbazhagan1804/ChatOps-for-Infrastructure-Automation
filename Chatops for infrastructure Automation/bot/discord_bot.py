#!/usr/bin/env python3

import os
import logging
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable

import discord
from discord.ext import commands

class DiscordBot:
    """Discord Bot implementation for ChatOps
    
    This class handles the Discord-specific integration, including:
    - Connecting to Discord API
    - Receiving and sending messages
    - Processing commands
    - Handling interactions
    """
    
    def __init__(self, config: Dict[str, Any], app):
        """Initialize the Discord bot with the given configuration
        
        Args:
            config: Discord configuration dictionary
            app: Main ChatOps application instance
        """
        self.logger = logging.getLogger('chatops.discord_bot')
        self.config = config
        self.app = app
        
        # Initialize Discord client
        self.bot_token = config.get('bot_token')
        self.command_prefix = config.get('command_prefix', '!')
        
        if not self.bot_token:
            self.logger.error("Missing required Discord bot token in configuration")
            raise ValueError("Missing required Discord bot token in configuration")
        
        # Get allowed channels from config
        self.allowed_channels = set(config.get('allowed_channels', []))
        self.logger.info(f"Allowed channels: {', '.join(self.allowed_channels)}")
        
        # Initialize Discord client with intents
        intents = discord.Intents.default()
        intents.message_content = True  # Enable message content intent
        intents.messages = True  # Enable messages intent
        
        self.client = commands.Bot(command_prefix=self.command_prefix, intents=intents)
        
        # Register event handlers
        self._register_event_handlers()
    
    def _register_event_handlers(self):
        """Register Discord event handlers"""
        @self.client.event
        async def on_ready():
            self.logger.info(f"Discord bot logged in as {self.client.user}")
            await self.client.change_presence(activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="infrastructure commands"
            ))
        
        @self.client.event
        async def on_message(message):
            # Ignore messages from the bot itself
            if message.author == self.client.user:
                return
            
            # Process commands with prefix
            if message.content.startswith(self.command_prefix):
                await self.client.process_commands(message)
                return
            
            # Check if message is in allowed channel
            if not self._is_channel_allowed(message.channel):
                return
            
            # Check if message is directed to the bot (mention or DM)
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mention = self.client.user.mentioned_in(message)
            
            if is_dm or is_mention:
                # Remove bot mention from text if present
                text = message.content
                if is_mention:
                    for mention in message.mentions:
                        if mention == self.client.user:
                            text = text.replace(f"<@{mention.id}>", "").strip()
                            text = text.replace(f"<@!{mention.id}>", "").strip()
                
                self.logger.info(f"Processing message from {message.author.id} in {message.channel.id}: {text}")
                
                # Show typing indicator
                async with message.channel.typing():
                    # Process the message in a separate thread to avoid blocking
                    response = await self._process_message_async(text, str(message.author.id), str(message.channel.id))
                    
                    # Send response back to Discord
                    await self.send_message(message.channel, response)
        
        # Register command handlers
        @self.client.command(name="help")
        async def help_command(ctx, *args):
            """Get help on available commands"""
            topic = args[0] if args else None
            response = self.app.command_parser.get_help(topic)
            await ctx.send(response)
        
        @self.client.command(name="deploy")
        async def deploy_command(ctx, *args):
            """Deploy a service to an environment"""
            if not self._is_channel_allowed(ctx.channel):
                return
            
            text = f"deploy {' '.join(args)}"
            response = await self._process_message_async(text, str(ctx.author.id), str(ctx.channel.id))
            await ctx.send(response)
        
        @self.client.command(name="status")
        async def status_command(ctx, *args):
            """Get status of services or environments"""
            if not self._is_channel_allowed(ctx.channel):
                return
            
            text = f"status {' '.join(args)}"
            response = await self._process_message_async(text, str(ctx.author.id), str(ctx.channel.id))
            await ctx.send(response)
        
        @self.client.command(name="scale")
        async def scale_command(ctx, *args):
            """Scale a service"""
            if not self._is_channel_allowed(ctx.channel):
                return
            
            text = f"scale {' '.join(args)}"
            response = await self._process_message_async(text, str(ctx.author.id), str(ctx.channel.id))
            await ctx.send(response)
        
        @self.client.command(name="provision")
        async def provision_command(ctx, *args):
            """Provision new infrastructure"""
            if not self._is_channel_allowed(ctx.channel):
                return
            
            text = f"provision {' '.join(args)}"
            response = await self._process_message_async(text, str(ctx.author.id), str(ctx.channel.id))
            await ctx.send(response)
    
    def _is_channel_allowed(self, channel) -> bool:
        """Check if the given channel is allowed for bot interaction
        
        Args:
            channel: Discord channel object
            
        Returns:
            True if channel is allowed, False otherwise
        """
        # If no allowed channels specified, allow all
        if not self.allowed_channels:
            return True
        
        # Always allow DMs
        if isinstance(channel, discord.DMChannel):
            return True
        
        # Check if channel name is in allowed list
        return channel.name in self.allowed_channels
    
    async def _process_message_async(self, text: str, user_id: str, channel_id: str) -> str:
        """Process a message asynchronously
        
        Args:
            text: Message text
            user_id: Discord user ID
            channel_id: Discord channel ID
            
        Returns:
            Response text
        """
        # Use a thread pool to run the synchronous process_message method
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.app.process_message, text, user_id, channel_id
        )
    
    async def send_message(self, channel, text: str, embed: Optional[discord.Embed] = None) -> bool:
        """Send a message to a Discord channel
        
        Args:
            channel: Discord channel object
            text: Message text
            embed: Optional embed for rich formatting
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            if embed:
                await channel.send(content=text, embed=embed)
            else:
                # Split long messages to comply with Discord's 2000 character limit
                if len(text) <= 2000:
                    await channel.send(content=text)
                else:
                    # Split message into chunks of 2000 characters
                    chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
                    for i, chunk in enumerate(chunks):
                        if i < len(chunks) - 1:
                            chunk += "... (continued)"
                        await channel.send(content=chunk)
            return True
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return False
    
    def create_embed(self, title: str, description: str, fields: Optional[List[Dict[str, str]]] = None, color: int = 0x3498db) -> discord.Embed:
        """Create a Discord embed for rich message formatting
        
        Args:
            title: Embed title
            description: Embed description
            fields: Optional list of fields (name, value, inline)
            color: Embed color (hex)
            
        Returns:
            Discord Embed object
        """
        embed = discord.Embed(title=title, description=description, color=color)
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', ''),
                    value=field.get('value', ''),
                    inline=field.get('inline', False)
                )
        
        return embed
    
    def start(self):
        """Start the Discord bot"""
        try:
            self.logger.info("Starting Discord bot")
            self.client.run(self.bot_token)
        except Exception as e:
            self.logger.error(f"Error starting Discord bot: {e}")
            raise