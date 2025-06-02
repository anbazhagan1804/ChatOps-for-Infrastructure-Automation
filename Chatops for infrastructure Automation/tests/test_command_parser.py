import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.command_parser import CommandParser


class TestCommandParser:
    
    @pytest.fixture
    def mock_config(self):
        return {
            "commands": {
                "templates_file": "bot/data/command_templates.json",
                "allowed_intents": ["deploy", "provision", "scale", "status", "help", "rollback", "destroy"]
            }
        }
    
    @pytest.fixture
    def mock_command_templates(self):
        return {
            "version": "1.0",
            "templates": [
                {
                    "intent": "deploy",
                    "command": {
                        "action": "deploy",
                        "parameters": {
                            "service": "{service}",
                            "environment": "{environment}",
                            "version": "{version}"
                        },
                        "workflow": "deploy_workflow"
                    },
                    "help": "Deploy a service to an environment",
                    "examples": [
                        "deploy api to production",
                        "deploy web-app version 1.2.3 to staging"
                    ]
                },
                {
                    "intent": "provision",
                    "command": {
                        "action": "provision",
                        "parameters": {
                            "resource": "{resource}",
                            "environment": "{environment}",
                            "count": "{count}",
                            "region": "{region}"
                        },
                        "workflow": "provision_workflow"
                    },
                    "help": "Provision infrastructure resources",
                    "examples": [
                        "provision 3 web-servers in production",
                        "create database in staging"
                    ]
                },
                {
                    "intent": "status",
                    "command": {
                        "action": "status",
                        "parameters": {
                            "resource": "{resource}",
                            "environment": "{environment}",
                            "detailed": "{detailed}"
                        },
                        "workflow": "status_workflow"
                    },
                    "help": "Check status of resources",
                    "examples": [
                        "check status of web-server in production",
                        "get status of staging"
                    ]
                },
                {
                    "intent": "help",
                    "command": {
                        "action": "help",
                        "parameters": {
                            "action": "{action}"
                        },
                        "workflow": "help_workflow"
                    },
                    "help": "Show help information",
                    "examples": [
                        "help",
                        "help with deploy"
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def command_parser(self, mock_config, mock_command_templates):
        with patch('builtins.open', MagicMock()), \
             patch('json.load') as mock_json_load:
            
            # Mock loading JSON files
            mock_json_load.return_value = mock_command_templates
            
            parser = CommandParser(mock_config)
            return parser
    
    def test_init(self, mock_config, mock_command_templates):
        with patch('builtins.open', MagicMock()), \
             patch('json.load') as mock_json_load:
            
            mock_json_load.return_value = mock_command_templates
            
            parser = CommandParser(mock_config)
            
            assert parser._config == mock_config
            assert parser._templates == mock_command_templates["templates"]
            assert len(parser._templates) == 4
    
    def test_parse_deploy_command(self, command_parser):
        intent = "deploy"
        entities = {
            "service": "api",
            "environment": "production",
            "version": "1.2.3"
        }
        
        command = command_parser.parse_command(intent, entities)
        
        assert command["action"] == "deploy"
        assert command["parameters"]["service"] == "api"
        assert command["parameters"]["environment"] == "production"
        assert command["parameters"]["version"] == "1.2.3"
        assert command["workflow"] == "deploy_workflow"
    
    def test_parse_deploy_command_with_defaults(self, command_parser):
        intent = "deploy"
        entities = {
            "service": "api",
            "environment": "production"
            # version is missing, should use default
        }
        
        command = command_parser.parse_command(intent, entities)
        
        assert command["action"] == "deploy"
        assert command["parameters"]["service"] == "api"
        assert command["parameters"]["environment"] == "production"
        assert "version" in command["parameters"]
        assert command["workflow"] == "deploy_workflow"
    
    def test_parse_provision_command(self, command_parser):
        intent = "provision"
        entities = {
            "resource": "web-server",
            "environment": "staging",
            "count": "3",
            "region": "us-east-1"
        }
        
        command = command_parser.parse_command(intent, entities)
        
        assert command["action"] == "provision"
        assert command["parameters"]["resource"] == "web-server"
        assert command["parameters"]["environment"] == "staging"
        assert command["parameters"]["count"] == "3"
        assert command["parameters"]["region"] == "us-east-1"
        assert command["workflow"] == "provision_workflow"
    
    def test_parse_status_command(self, command_parser):
        intent = "status"
        entities = {
            "resource": "web-server",
            "environment": "production",
            "detailed": "true"
        }
        
        command = command_parser.parse_command(intent, entities)
        
        assert command["action"] == "status"
        assert command["parameters"]["resource"] == "web-server"
        assert command["parameters"]["environment"] == "production"
        assert command["parameters"]["detailed"] == "true"
        assert command["workflow"] == "status_workflow"
    
    def test_parse_help_command(self, command_parser):
        intent = "help"
        entities = {
            "action": "deploy"
        }
        
        command = command_parser.parse_command(intent, entities)
        
        assert command["action"] == "help"
        assert command["parameters"]["action"] == "deploy"
        assert command["workflow"] == "help_workflow"
    
    def test_parse_help_command_no_action(self, command_parser):
        intent = "help"
        entities = {}
        
        command = command_parser.parse_command(intent, entities)
        
        assert command["action"] == "help"
        assert "action" in command["parameters"]
        assert command["workflow"] == "help_workflow"
    
    def test_parse_unknown_intent(self, command_parser):
        intent = "unknown"
        entities = {}
        
        command = command_parser.parse_command(intent, entities)
        
        assert command is None
    
    def test_get_help_text_for_intent(self, command_parser):
        help_text = command_parser.get_help_text("deploy")
        
        assert "Deploy a service to an environment" in help_text
        assert "Examples:" in help_text
        assert "deploy api to production" in help_text
        assert "deploy web-app version 1.2.3 to staging" in help_text
    
    def test_get_help_text_all(self, command_parser):
        help_text = command_parser.get_help_text()
        
        assert "Available Commands:" in help_text
        assert "deploy" in help_text
        assert "provision" in help_text
        assert "status" in help_text
        assert "help" in help_text
    
    def test_get_help_text_unknown_intent(self, command_parser):
        help_text = command_parser.get_help_text("unknown")
        
        assert "Unknown command: unknown" in help_text
        assert "Available Commands:" in help_text


if __name__ == "__main__":
    pytest.main(['-xvs', __file__])