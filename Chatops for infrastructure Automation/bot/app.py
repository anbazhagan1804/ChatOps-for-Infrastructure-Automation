#!/usr/bin/env python3

import os
import sys
import yaml
import logging
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import bot modules
from bot.nlp_processor import NLPProcessor
from bot.command_parser import CommandParser
from bot.slack_bot import SlackBot
from bot.discord_bot import DiscordBot
from bot.workflow_manager import WorkflowManager

# Configure logging
def setup_logging(config):
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_file = log_config.get('file', './logs/chatops.log')
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('chatops')

# Load configuration
def load_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            return yaml.safe_load(config_file)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

# Main application class
class ChatOpsApp:
    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.logger = setup_logging(self.config)
        self.logger.info("Initializing ChatOps application")
        
        # Initialize NLP processor
        self.nlp = NLPProcessor(self.config.get('nlp', {}))
        self.logger.info("NLP processor initialized")
        
        # Initialize command parser
        self.command_parser = CommandParser(self.config.get('nlp', {}))
        self.logger.info("Command parser initialized")
        
        # Initialize workflow manager
        self.workflow_manager = WorkflowManager(self.config.get('workflows', {}), self.config.get('integrations', {}))
        self.logger.info("Workflow manager initialized")
        
        # Initialize the appropriate bot based on configuration
        self.bot = self._initialize_bot()
        
    def _initialize_bot(self):
        bot_config = self.config.get('bots', {})
        if bot_config.get('slack', {}).get('enabled'):
            self.logger.info("Initializing Slack bot")
            return SlackBot(bot_config['slack'], self)
        elif bot_config.get('discord', {}).get('enabled'):
            self.logger.info("Initializing Discord bot")
            return DiscordBot(bot_config['discord'], self)
        else:
            self.logger.error("No bot platform enabled in configuration.")
            raise ValueError("No bot platform enabled in configuration. Please check config.yaml")
    
    def process_message(self, message, user_id, channel_id):
        """Process incoming message from chat platform"""
        self.logger.info(f"Processing message: '{message}' from user {user_id} in channel {channel_id}")
        
        # Check if user is authorized
        if not self._is_user_authorized(user_id, message):
            return "You are not authorized to perform this action."
        
        # Process message with NLP
        intent, entities, confidence = self.nlp.process(message)
        self.logger.debug(f"NLP result: intent={intent}, entities={entities}, confidence={confidence}")
        
        # If confidence is too low, ask for clarification
        if confidence < self.config['nlp']['confidence_threshold']:
            return f"I'm not sure what you want to do. Could you please be more specific?"
        
        # Parse command using the command parser
        command = self.command_parser.parse(intent, entities)
        if not command:
            return "I couldn't understand your command. Please try again."
        
        # Check if command requires approval
        if self._requires_approval(message):
            self.logger.info(f"Command requires approval: {message}")
            return f"This command requires approval. Please have an admin confirm this action."
        
        # Execute the command through workflow manager
        try:
            result = self.workflow_manager.execute(command)
            return result
        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            return f"Error executing command: {str(e)}"
    
    def _is_user_authorized(self, user_id, message):
        """Check if user is authorized to perform the action"""
        # Check if user is in authorized users list
        authorized_users = self.config['security']['authorized_users']
        if user_id not in authorized_users:
            self.logger.warning(f"Unauthorized user {user_id} attempted to use bot")
            return False
        
        # Check for restricted commands that require admin privileges
        restricted_commands = self.config['security']['restricted_commands']
        admin_users = self.config['security']['admin_users']
        
        for restricted in restricted_commands:
            if restricted.lower() in message.lower() and user_id not in admin_users:
                self.logger.warning(f"User {user_id} attempted restricted command: {message}")
                return False
        
        return True
    
    def _requires_approval(self, message):
        """Check if command requires approval"""
        approval_required = self.config['security']['approval_required']
        for command in approval_required:
            if command.lower() in message.lower():
                return True
        return False
    
    def run(self):
        """Start the bot"""
        self.logger.info("Starting ChatOps bot")
        self.bot.start()

def start_api_server(app_instance):
    import uvicorn
    from bot.api import app as fastapi_app # Import the FastAPI app object from api.py
    # The chatops_app_instance in api.py should already be set by initialize_chatops_app_globally
    # when api.py was imported. We are passing our app_instance for consistency, though
    # api.py's get_chatops_app will likely use its own global.
    # This needs careful management if app_instance here and in api.py are different.
    
    # A better way: api.py should expose a function to set its global instance, or get_chatops_app should be more flexible.
    # For now, let's assume api.py's global initialization is sufficient.
    
    logger = logging.getLogger('chatops.main')
    logger.info("Starting FastAPI server via app.py...")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=app_instance.config.get('app',{}).get('api_port', 8080), log_level="info")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ChatOps Bot")
    parser.add_argument('--config', default=os.getenv('CONFIG_FILE', 'config.yaml'), help='Path to configuration file')
    parser.add_argument('--serve-api', action='store_true', help='Run the FastAPI server instead of the bot listeners.')
    # Add a flag to run only the bot, or both, if desired.
    # parser.add_argument('--run-bot', action='store_true', help='Run the bot listeners.')

    args = parser.parse_args()

    # Ensure config path is absolute or resolved correctly if app.py is not in project root
    config_main_path = args.config
    if not os.path.isabs(config_main_path):
        config_main_path = os.path.abspath(os.path.join(project_root, config_main_path))

    # Initialize ChatOpsApp. This instance will be used by either the bot or the API server.
    # api.py also initializes its own instance when imported. This could be problematic.
    # A singleton pattern for ChatOpsApp or a shared context would be better.
    main_app_instance = ChatOpsApp(config_main_path)

    if args.serve_api:
        # If api.py's global chatops_app_instance is what FastAPI uses,
        # ensure it's the same as main_app_instance or properly configured.
        # This is tricky. For now, we assume api.py's initialization is primary for the API.
        # The `initialize_chatops_app_globally()` in api.py runs on import.
        # So, when `from bot.api import app as fastapi_app` runs, it's already set up.
        start_api_server(main_app_instance) # Pass our instance for port config, etc.
    else:
        # Default behavior: run the bot
        main_app_instance.run() # This should start the Slack/Discord bot listeners