#!/usr/bin/env python3

import os
import logging
import spacy
import json
from pathlib import Path
from typing import Tuple, Dict, List, Any, Optional
from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer

class NLPProcessor:
    def __init__(self, nlp_config):
        self.config = nlp_config
        self.model_name = self.config.get('model', 'en_core_web_sm')
        self.confidence_threshold = self.config.get('confidence_threshold', 0.7)
        self.command_patterns_file = self.config.get('command_patterns_file', 'bot/data/command_patterns.json')
        self.custom_entities_file = self.config.get('custom_entities_file', 'bot/data/custom_entities.json')
        self.logger = logging.getLogger(__name__)
    
    def _add_custom_entities(self):
        """Add custom entities to the NLP pipeline"""
        for entity in self.custom_entities:
            self.logger.debug(f"Adding custom entity: {entity['name']}")
            values = entity.get('values', [])
            patterns = [(value, {"label": entity['name']}) for value in values]
            
            # Add entity ruler to pipeline if not already present
            if 'entity_ruler' not in self.nlp.pipe_names:
                ruler = self.nlp.add_pipe('entity_ruler', before='ner')
            else:
                ruler = self.nlp.get_pipe('entity_ruler')
            
            ruler.add_patterns(patterns)
    
    def _load_intent_classifier(self):
        """Load the intent classification model"""
        try:
            # Check if we have a custom model path
            model_path = self.config.get('intent_model_path')
            if model_path and os.path.exists(model_path):
                self.logger.info(f"Loading custom intent model from {model_path}")
                self.intent_model = AutoModelForSequenceClassification.from_pretrained(model_path)
                self.intent_tokenizer = AutoTokenizer.from_pretrained(model_path)
            else:
                # Use default model from Hugging Face
                self.logger.info("Loading default intent classification model")
                model_name = "distilbert-base-uncased-finetuned-sst-2-english"
                self.intent_classifier = pipeline(
                    "text-classification", 
                    model=model_name,
                    tokenizer=model_name
                )
        except Exception as e:
            self.logger.error(f"Error loading intent classifier: {e}")
            # Fallback to rule-based classification
            self.logger.warning("Falling back to rule-based intent classification")
            self.intent_classifier = None
    
    def _load_command_patterns(self):
        """Load command patterns from file"""
        try:
            patterns_file = self.config.get('patterns_file', './config/command_patterns.json')
            with open(patterns_file, 'r') as f:
                self.command_patterns = json.load(f)
            self.logger.info(f"Loaded {len(self.command_patterns)} command patterns")
        except Exception as e:
            self.logger.error(f"Error loading command patterns: {e}")
            # Initialize with default patterns
            self.command_patterns = self._get_default_patterns()
            self.logger.warning(f"Using {len(self.command_patterns)} default command patterns")
    
    def _get_default_patterns(self) -> List[Dict[str, Any]]:
        """Return default command patterns if no file is available"""
        return [
            {
                "intent": "deploy",
                "patterns": [
                    "deploy {service} to {environment}",
                    "release {service} to {environment}",
                    "push {service} to {environment}"
                ]
            },
            {
                "intent": "scale",
                "patterns": [
                    "scale {service} to {count} replicas",
                    "scale {service} {direction}",
                    "increase {service} capacity",
                    "decrease {service} capacity"
                ]
            },
            {
                "intent": "status",
                "patterns": [
                    "show status of {environment}",
                    "get status of {service}",
                    "check {service} in {environment}",
                    "how is {service} doing"
                ]
            },
            {
                "intent": "provision",
                "patterns": [
                    "provision new {resource}",
                    "create {count} {resource}",
                    "setup {resource} in {environment}"
                ]
            },
            {
                "intent": "help",
                "patterns": [
                    "help",
                    "show commands",
                    "what can you do",
                    "list commands"
                ]
            }
        ]
    
    def _classify_intent(self, text: str) -> Tuple[str, float]:
        """Classify the intent of the given text
        
        Args:
            text: The text to classify
            
        Returns:
            Tuple of (intent, confidence)
        """
        if self.intent_classifier:
            # Use transformer model for classification
            try:
                result = self.intent_classifier(text)[0]
                return result['label'], result['score']
            except Exception as e:
                self.logger.error(f"Error in intent classification: {e}")
                # Fall back to rule-based
                pass
        
        # Rule-based intent classification
        best_intent = "unknown"
        best_score = 0.0
        
        # Process with spaCy for better text normalization
        doc = self.nlp(text)
        normalized_text = " ".join([token.lemma_.lower() for token in doc])
        
        for pattern in self.command_patterns:
            intent = pattern["intent"]
            for pattern_text in pattern["patterns"]:
                # Simple string matching for now
                # In a real implementation, this would use more sophisticated matching
                pattern_words = set(pattern_text.lower().split())
                text_words = set(normalized_text.split())
                
                # Calculate Jaccard similarity
                intersection = pattern_words.intersection(text_words)
                union = pattern_words.union(text_words)
                similarity = len(intersection) / len(union) if union else 0
                
                if similarity > best_score:
                    best_score = similarity
                    best_intent = intent
        
        return best_intent, best_score
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from the given text
        
        Args:
            text: The text to extract entities from
            
        Returns:
            Dictionary of entity types to values
        """
        doc = self.nlp(text)
        entities = {}
        
        # Extract named entities
        for ent in doc.ents:
            entities[ent.label_.lower()] = ent.text
        
        # Extract custom entities
        for entity in self.custom_entities:
            entity_name = entity['name']
            if entity_name not in entities:
                for value in entity.get('values', []):
                    if value.lower() in text.lower():
                        entities[entity_name] = value
                        break
        
        # Extract numbers for scaling operations
        if 'scale' in text.lower():
            for token in doc:
                if token.like_num:
                    entities['count'] = token.text
                    break
        
        # Extract direction for scaling (up/down)
        if 'up' in text.lower() or 'increase' in text.lower():
            entities['direction'] = 'up'
        elif 'down' in text.lower() or 'decrease' in text.lower():
            entities['direction'] = 'down'
        
        return entities
    
    def process(self, text: str) -> Tuple[str, Dict[str, Any], float]:
        """Process the given text to extract intent and entities
        
        Args:
            text: The text to process
            
        Returns:
            Tuple of (intent, entities, confidence)
        """
        self.logger.debug(f"Processing text: {text}")
        
        # Classify intent
        intent, confidence = self._classify_intent(text)
        self.logger.debug(f"Classified intent: {intent} (confidence: {confidence:.2f})")
        
        # Extract entities
        entities = self._extract_entities(text)
        self.logger.debug(f"Extracted entities: {entities}")
        
        return intent, entities, confidence
    
    def train(self, training_data: List[Dict[str, Any]]) -> None:
        """Train the NLP model with new examples
        
        Args:
            training_data: List of training examples with intent and text
        """
        # This would be implemented in a real system to allow for model improvement
        # For now, just log that training was requested
        self.logger.info(f"Training requested with {len(training_data)} examples")
        self.logger.warning("Training not implemented in this version")