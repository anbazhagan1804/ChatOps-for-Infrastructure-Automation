import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.nlp_processor import NLPProcessor


class TestNLPProcessor:
    
    @pytest.fixture
    def mock_config(self):
        return {
            "nlp": {
                "spacy_model": "en_core_web_sm",
                "intent_model": "default",
                "confidence_threshold": 0.7,
                "custom_entities_file": "bot/data/custom_entities.json",
                "command_patterns_file": "bot/data/command_patterns.json"
            }
        }
    
    @pytest.fixture
    def mock_custom_entities(self):
        return {
            "version": "1.0",
            "entities": [
                {
                    "name": "service",
                    "description": "Application services that can be deployed",
                    "values": [
                        {
                            "value": "api",
                            "synonyms": ["api-service", "api server"]
                        },
                        {
                            "value": "web-app",
                            "synonyms": ["webapp", "web app"]
                        }
                    ]
                },
                {
                    "name": "environment",
                    "description": "Deployment environments",
                    "values": [
                        {
                            "value": "development",
                            "synonyms": ["dev", "develop"]
                        },
                        {
                            "value": "production",
                            "synonyms": ["prod", "live"]
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def mock_command_patterns(self):
        return {
            "version": "1.0",
            "patterns": [
                {
                    "intent": "deploy",
                    "patterns": [
                        "deploy {service} to {environment}",
                        "deploy {service} version {version} to {environment}"
                    ],
                    "entities": [
                        {
                            "name": "service",
                            "required": True
                        },
                        {
                            "name": "environment",
                            "required": True,
                            "default": "development"
                        },
                        {
                            "name": "version",
                            "required": False,
                            "default": "latest"
                        }
                    ]
                },
                {
                    "intent": "status",
                    "patterns": [
                        "check status of {service} in {environment}",
                        "get status of {environment}"
                    ],
                    "entities": [
                        {
                            "name": "service",
                            "required": False
                        },
                        {
                            "name": "environment",
                            "required": True,
                            "default": "development"
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def nlp_processor(self, mock_config, mock_custom_entities, mock_command_patterns):
        with patch('bot.nlp_processor.spacy.load') as mock_spacy_load, \
             patch('builtins.open', MagicMock()), \
             patch('json.load') as mock_json_load:
            
            # Mock spaCy model
            mock_nlp = MagicMock()
            mock_spacy_load.return_value = mock_nlp
            
            # Mock loading JSON files
            mock_json_load.side_effect = [mock_custom_entities, mock_command_patterns]
            
            # Mock intent classifier
            mock_intent_classifier = MagicMock()
            mock_intent_classifier.predict.return_value = ("deploy", 0.85)
            
            processor = NLPProcessor(mock_config)
            processor._intent_classifier = mock_intent_classifier
            
            return processor
    
    def test_init(self, mock_config):
        with patch('bot.nlp_processor.spacy.load') as mock_spacy_load, \
             patch('builtins.open', MagicMock()), \
             patch('json.load', MagicMock(return_value={})):
            
            processor = NLPProcessor(mock_config)
            
            assert processor._config == mock_config
            mock_spacy_load.assert_called_once_with(mock_config["nlp"]["spacy_model"])
    
    def test_classify_intent(self, nlp_processor):
        text = "deploy api to production"
        intent, confidence = nlp_processor._classify_intent(text)
        
        assert intent == "deploy"
        assert confidence == 0.85
        nlp_processor._intent_classifier.predict.assert_called_once_with(text)
    
    def test_extract_entities_from_pattern(self, nlp_processor):
        text = "deploy api to production"
        pattern = "deploy {service} to {environment}"
        
        entities = nlp_processor._extract_entities_from_pattern(text, pattern)
        
        assert entities == {"service": "api", "environment": "production"}
    
    def test_extract_entities_from_pattern_with_version(self, nlp_processor):
        text = "deploy api version 1.2.3 to production"
        pattern = "deploy {service} version {version} to {environment}"
        
        entities = nlp_processor._extract_entities_from_pattern(text, pattern)
        
        assert entities == {"service": "api", "version": "1.2.3", "environment": "production"}
    
    def test_extract_entities(self, nlp_processor):
        text = "deploy api to production"
        intent = "deploy"
        
        entities = nlp_processor._extract_entities(text, intent)
        
        assert entities == {"service": "api", "environment": "production"}
    
    def test_extract_entities_with_default_values(self, nlp_processor):
        text = "deploy api"
        intent = "deploy"
        
        # This should fail to match any pattern exactly, but the NLP processor should
        # still try to extract entities and apply defaults
        entities = nlp_processor._extract_entities(text, intent)
        
        # The environment should get the default value "development"
        assert "service" in entities
        assert entities["service"] == "api"
        assert "environment" in entities
        assert entities["environment"] == "development"
    
    def test_process_text_deploy(self, nlp_processor):
        text = "deploy api to production"
        
        result = nlp_processor.process_text(text)
        
        assert result["intent"] == "deploy"
        assert result["confidence"] > 0.7
        assert result["entities"]["service"] == "api"
        assert result["entities"]["environment"] == "production"
    
    def test_process_text_status(self, nlp_processor):
        # Override the mock intent classifier to return "status"
        nlp_processor._intent_classifier.predict.return_value = ("status", 0.9)
        
        text = "check status of api in production"
        
        result = nlp_processor.process_text(text)
        
        assert result["intent"] == "status"
        assert result["confidence"] > 0.7
        assert result["entities"]["service"] == "api"
        assert result["entities"]["environment"] == "production"
    
    def test_process_text_low_confidence(self, nlp_processor):
        # Override the mock intent classifier to return low confidence
        nlp_processor._intent_classifier.predict.return_value = ("deploy", 0.5)
        
        text = "do something unclear"
        
        result = nlp_processor.process_text(text)
        
        assert result["intent"] is None
        assert result["confidence"] == 0.5
        assert result["entities"] == {}
    
    def test_normalize_entity_value(self, nlp_processor):
        # Test with direct match
        assert nlp_processor._normalize_entity_value("service", "api") == "api"
        
        # Test with synonym match
        assert nlp_processor._normalize_entity_value("service", "api server") == "api"
        
        # Test with no match
        assert nlp_processor._normalize_entity_value("service", "unknown-service") == "unknown-service"
        
        # Test with environment
        assert nlp_processor._normalize_entity_value("environment", "dev") == "development"
        assert nlp_processor._normalize_entity_value("environment", "prod") == "production"


if __name__ == "__main__":
    pytest.main(['-xvs', __file__])