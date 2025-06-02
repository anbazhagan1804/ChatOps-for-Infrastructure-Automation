#!/usr/bin/env python3

import os
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Callable

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.web.slack_response import SlackResponse

class SlackBot:
    """Slack Bot implementation for ChatOps
    
    This class handles the Slack-specific integration, including:
    - Connecting to Slack API
    - Receiving and sending messages
    - Processing commands
    - Handling interactive components
    """
    
    def __init__(self, config: Dict[str, Any], app):
        """Initialize the Slack bot with the given configuration
        
        Args:
            config: Slack configuration dictionary
            app: Main ChatOps application instance
        """
        self.logger = logging.getLogger('chatops.slack_bot')
        self.config = config
        self.app = app
        
        # Initialize Slack clients
        self.bot_token = config.get('bot_token')
        self.app_token = config.get('app_token')
        
        if not self.bot_token or not self.app_token:
            self.logger.error("Missing required Slack tokens in configuration")
            raise ValueError("Missing required Slack tokens in configuration")
        
        self.web_client = WebClient(token=self.bot_token)
        self.socket_client = None
        
        # Get allowed channels from config
        self.allowed_channels = set(config.get('allowed_channels', []))
        self.logger.info(f"Allowed channels: {', '.join(self.allowed_channels)}")
        
        # Initialize channel cache
        self.channel_cache = {}
        self._refresh_channel_cache()
    
    def _refresh_channel_cache(self):
        """Refresh the channel name to ID mapping cache"""
        try:
            # Get public channels
            response = self.web_client.conversations_list()
            for channel in response['channels']:
                self.channel_cache[channel['name']] = channel['id']
            
            # Get private channels the bot is a member of
            response = self.web_client.conversations_list(types="private_channel")
            for channel in response['channels']:
                self.channel_cache[channel['name']] = channel['id']
                
            self.logger.debug(f"Refreshed channel cache with {len(self.channel_cache)} channels")
        except SlackApiError as e:
            self.logger.error(f"Error refreshing channel cache: {e}")
    
    def _is_channel_allowed(self, channel_id: str) -> bool:
        """Check if the given channel is allowed for bot interaction
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            True if channel is allowed, False otherwise
        """
        # If no allowed channels specified, allow all
        if not self.allowed_channels:
            return True
        
        # Get channel info
        try:
            response = self.web_client.conversations_info(channel=channel_id)
            channel_name = response['channel']['name']
            return channel_name in self.allowed_channels
        except SlackApiError as e:
            self.logger.error(f"Error checking channel: {e}")
            return False
    
    def _handle_message(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming message events
        
        Args:
            client: Socket mode client
            req: Socket mode request
        """
        # Acknowledge the request
        client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
        
        # Extract event data
        event = req.payload.get("event", {})
        event_type = event.get("type")
        
        # Only process message events
        if event_type != "message":
            return
        
        # Ignore bot messages to prevent loops
        if event.get("bot_id"):
            return
        
        # Get message details
        user_id = event.get("user")
        channel_id = event.get("channel")
        text = event.get("text", "").strip()
        
        # Check if channel is allowed
        if not self._is_channel_allowed(channel_id):
            self.logger.warning(f"Message received in non-allowed channel {channel_id}")
            return
        
        # Check if message is directed to the bot
        is_dm = self._is_direct_message(channel_id)
        is_mention = f"<@{self._get_bot_user_id()}>" in text
        
        if is_dm or is_mention:
            # Remove bot mention from text if present
            if is_mention:
                text = text.replace(f"<@{self._get_bot_user_id()}>", "").strip()
            
            self.logger.info(f"Processing message from {user_id} in {channel_id}: {text}")
            
            # Process the message
            threading.Thread(target=self._process_message, args=(text, user_id, channel_id)).start()
    
    def _process_message(self, text: str, user_id: str, channel_id: str):
        """Process a message and send the response
        
        Args:
            text: Message text
            user_id: Slack user ID
            channel_id: Slack channel ID
        """
        try:
            # Send typing indicator
            self.web_client.conversations_mark(channel=channel_id)
            
            # Process message through the main app
            response = self.app.process_message(text, user_id, channel_id)
            
            # Send response back to Slack
            self.send_message(channel_id, response)
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            self.send_message(channel_id, f"Error processing your request: {str(e)}")
    
    def _is_direct_message(self, channel_id: str) -> bool:
        """Check if the given channel is a direct message
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            True if channel is a DM, False otherwise
        """
        try:
            response = self.web_client.conversations_info(channel=channel_id)
            return response['channel'].get('is_im', False)
        except SlackApiError:
            return False
    
    def _get_bot_user_id(self) -> str:
        """Get the bot's user ID
        
        Returns:
            Bot user ID
        """
        try:
            response = self.web_client.auth_test()
            return response['user_id']
        except SlackApiError as e:
            self.logger.error(f"Error getting bot user ID: {e}")
            return ""
    
    def send_message(self, channel_id: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Send a message to a Slack channel
        
        Args:
            channel_id: Slack channel ID
            text: Message text
            blocks: Optional message blocks for rich formatting
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            self.web_client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks
            )
            return True
        except SlackApiError as e:
            self.logger.error(f"Error sending message: {e}")
            return False
    
    def start(self):
        """Start the Slack bot"""
        try:
            # Initialize Socket Mode client
            self.socket_client = SocketModeClient(
                app_token=self.app_token,
                web_client=self.web_client
            )
            
            # Register event handlers
            self.socket_client.socket_mode_request_listeners.append(self._handle_message)
            
            # Start Socket Mode client in a separate thread
            self.logger.info("Starting Slack bot in Socket Mode")
            threading.Thread(target=self.socket_client.connect, daemon=True).start()
            
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error starting Slack bot: {e}")
            raise