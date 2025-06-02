#!/usr/bin/env python3

import logging
from typing import Dict, Any, Optional, List

class CommandParser:
    def __init__(self, nlp_config):
        self.config = nlp_config
        self.command_templates_file = self.config.get('command_templates_file', 'bot/data/command_templates.json')
        self.command_templates = self._load_command_templates()
        self.logger = logging.getLogger(__name__)
    
    def _load_command_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load command templates from configuration
        
        Returns:
            Dictionary of intent to command template mapping
        """
        # In a real implementation, this might load from a file or database
        # For now, we'll define some basic templates
        return {
            "deploy": {
                "action": "deploy",
                "required_entities": ["service"],
                "optional_entities": ["environment", "version"],
                "defaults": {
                    "environment": "development",
                    "version": "latest"
                },
                "workflow": "deploy_workflow.yaml"
            },
            "scale": {
                "action": "scale",
                "required_entities": ["service"],
                "optional_entities": ["count", "direction", "environment"],
                "defaults": {
                    "environment": "development",
                    "count": "1",
                    "direction": "up"
                },
                "workflow": "scale_workflow.yaml"
            },
            "status": {
                "action": "status",
                "required_entities": [],
                "optional_entities": ["service", "environment"],
                "defaults": {
                    "environment": "development"
                },
                "workflow": "status_workflow.yaml"
            },
            "provision": {
                "action": "provision",
                "required_entities": ["resource"],
                "optional_entities": ["count", "environment", "region"],
                "defaults": {
                    "environment": "development",
                    "count": "1",
                    "region": "us-east-1"
                },
                "workflow": "provision_workflow.yaml"
            },
            "help": {
                "action": "help",
                "required_entities": [],
                "optional_entities": ["topic"],
                "defaults": {},
                "workflow": None  # Help is handled directly, not via workflow
            }
        }
    
    def parse(self, intent: str, entities: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse the intent and entities into a structured command
        
        Args:
            intent: The classified intent
            entities: Dictionary of extracted entities
            
        Returns:
            Command dictionary or None if parsing fails
        """
        self.logger.debug(f"Parsing intent '{intent}' with entities: {entities}")
        
        # Check if we have a template for this intent
        if intent not in self.command_templates:
            self.logger.warning(f"No template found for intent: {intent}")
            return None
        
        template = self.command_templates[intent]
        
        # Check required entities
        for required in template["required_entities"]:
            if required not in entities:
                self.logger.warning(f"Missing required entity '{required}' for intent '{intent}'")
                return None
        
        # Build command with defaults and provided entities
        command = {
            "action": template["action"],
            "parameters": {}
        }
        
        # Add default values
        for key, value in template.get("defaults", {}).items():
            command["parameters"][key] = value
        
        # Override with provided entities
        for key, value in entities.items():
            command["parameters"][key] = value
        
        # Add workflow template if applicable
        if template.get("workflow"):
            command["workflow"] = template["workflow"]
        
        self.logger.debug(f"Parsed command: {command}")
        return command
    
    def get_help(self, topic: Optional[str] = None) -> str:
        """Get help text for available commands or a specific topic
        
        Args:
            topic: Optional topic to get help for
            
        Returns:
            Help text as a string
        """
        if topic:
            # Return help for specific topic/intent
            if topic in self.command_templates:
                template = self.command_templates[topic]
                required = ", ".join(template["required_entities"]) or "none"
                optional = ", ".join(template["optional_entities"]) or "none"
                
                return f"Help for '{topic}':\n" \
                       f"Description: Perform a {topic} action\n" \
                       f"Required parameters: {required}\n" \
                       f"Optional parameters: {optional}\n" \
                       f"Example: {self._get_example(topic)}"
            else:
                return f"No help available for topic '{topic}'"
        else:
            # Return general help
            help_text = "Available commands:\n\n"
            
            for intent, template in self.command_templates.items():
                help_text += f"- {intent.capitalize()}: {self._get_example(intent)}\n"
            
            help_text += "\nFor more details on a specific command, type 'help <command>'"
            return help_text
    
    def _get_example(self, intent: str) -> str:
        """Get an example command for the given intent
        
        Args:
            intent: The intent to get an example for
            
        Returns:
            Example command as a string
        """
        examples = {
            "deploy": "deploy api service to production",
            "scale": "scale web service to 3 replicas",
            "status": "show status of dev environment",
            "provision": "provision new database server",
            "help": "help deploy"
        }
        
        return examples.get(intent, f"<{intent} command>")