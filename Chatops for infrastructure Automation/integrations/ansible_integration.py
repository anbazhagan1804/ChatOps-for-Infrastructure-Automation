#!/usr/bin/env python3

import os
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

class AnsibleIntegration:
    """Ansible Integration for ChatOps
    
    This class handles interactions with Ansible for configuration management, including:
    - Running playbooks
    - Managing inventories
    - Executing ad-hoc commands
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Ansible integration with the given configuration
        
        Args:
            config: Ansible configuration dictionary
        """
        self.logger = logging.getLogger('chatops.ansible_integration')
        self.config = config
        
        # Set paths from config
        self.inventory_path = Path(config.get('inventory_path', './ansible/inventory'))
        self.playbooks_path = Path(config.get('playbooks_path', './ansible/playbooks'))
        
        # Create directories if they don't exist
        self.inventory_path.mkdir(parents=True, exist_ok=True)
        self.playbooks_path.mkdir(parents=True, exist_ok=True)
        
        # Load playbook mappings
        self.playbooks = config.get('playbooks', {})
        self.default_playbook = config.get('default_playbook')
        
        self.logger.info(f"Ansible integration initialized with {len(self.playbooks)} playbooks")
    
    def run_playbook(self, playbook: str, inventory: Optional[str] = None, extra_vars: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run an Ansible playbook
        
        Args:
            playbook: Name or path of the playbook
            inventory: Name or path of the inventory
            extra_vars: Extra variables to pass to the playbook
            
        Returns:
            Result dictionary
        """
        # Resolve playbook path
        playbook_path = self._resolve_playbook_path(playbook)
        if not playbook_path.exists():
            self.logger.error(f"Playbook not found: {playbook_path}")
            return {'success': False, 'message': f"Playbook not found: {playbook}"}
        
        # Resolve inventory path
        inventory_path = self._resolve_inventory_path(inventory)
        if not inventory_path.exists():
            self.logger.warning(f"Inventory not found: {inventory_path}, using default")
            inventory_path = None  # Let Ansible use the default inventory
        
        # Prepare command
        cmd = ['ansible-playbook', str(playbook_path)]
        
        if inventory_path:
            cmd.extend(['-i', str(inventory_path)])
        
        # Add extra vars if provided
        if extra_vars:
            # Create a temporary file for extra vars
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(extra_vars, f)
                extra_vars_file = f.name
            
            cmd.extend(['--extra-vars', f'@{extra_vars_file}'])
        else:
            extra_vars_file = None
        
        # Run the playbook
        try:
            self.logger.info(f"Running playbook: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up extra vars file if created
            if extra_vars_file and os.path.exists(extra_vars_file):
                os.unlink(extra_vars_file)
            
            if result.returncode == 0:
                self.logger.info(f"Playbook {playbook} completed successfully")
                return {
                    'success': True,
                    'message': f"Playbook {playbook} completed successfully",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                self.logger.error(f"Playbook {playbook} failed with return code {result.returncode}")
                return {
                    'success': False,
                    'message': f"Playbook {playbook} failed with return code {result.returncode}",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
        
        except Exception as e:
            self.logger.error(f"Error running playbook {playbook}: {e}")
            
            # Clean up extra vars file if created
            if extra_vars_file and os.path.exists(extra_vars_file):
                os.unlink(extra_vars_file)
            
            return {'success': False, 'message': f"Error running playbook: {str(e)}"}
    
    def run_ad_hoc_command(self, command: str, inventory: Optional[str] = None, hosts: str = 'all') -> Dict[str, Any]:
        """Run an Ansible ad-hoc command
        
        Args:
            command: Ansible module and arguments
            inventory: Name or path of the inventory
            hosts: Host pattern
            
        Returns:
            Result dictionary
        """
        # Resolve inventory path
        inventory_path = self._resolve_inventory_path(inventory)
        if not inventory_path.exists():
            self.logger.warning(f"Inventory not found: {inventory_path}, using default")
            inventory_path = None  # Let Ansible use the default inventory
        
        # Prepare command
        cmd = ['ansible', hosts, '-m', 'shell', '-a', command]
        
        if inventory_path:
            cmd.extend(['-i', str(inventory_path)])
        
        # Run the command
        try:
            self.logger.info(f"Running ad-hoc command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"Ad-hoc command completed successfully")
                return {
                    'success': True,
                    'message': f"Ad-hoc command completed successfully",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                self.logger.error(f"Ad-hoc command failed with return code {result.returncode}")
                return {
                    'success': False,
                    'message': f"Ad-hoc command failed with return code {result.returncode}",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
        
        except Exception as e:
            self.logger.error(f"Error running ad-hoc command: {e}")
            return {'success': False, 'message': f"Error running ad-hoc command: {str(e)}"}
    
    def _resolve_playbook_path(self, playbook: str) -> Path:
        """Resolve the path to a playbook
        
        Args:
            playbook: Name or path of the playbook
            
        Returns:
            Path to the playbook
        """
        # Check if playbook is a mapped name
        if playbook in self.playbooks:
            playbook = self.playbooks[playbook]
        
        # Check if playbook is a full path
        if os.path.isabs(playbook):
            return Path(playbook)
        
        # Check if playbook is in the playbooks directory
        playbook_path = self.playbooks_path / playbook
        if playbook_path.exists():
            return playbook_path
        
        # Check if playbook needs .yml extension
        if not playbook.endswith('.yml'):
            playbook_with_ext = f"{playbook}.yml"
            playbook_path = self.playbooks_path / playbook_with_ext
            if playbook_path.exists():
                return playbook_path
        
        # Return the original path even if it doesn't exist
        return self.playbooks_path / playbook
    
    def _resolve_inventory_path(self, inventory: Optional[str]) -> Path:
        """Resolve the path to an inventory
        
        Args:
            inventory: Name or path of the inventory
            
        Returns:
            Path to the inventory
        """
        if not inventory:
            # Use default inventory
            return self.inventory_path
        
        # Check if inventory is a full path
        if os.path.isabs(inventory):
            return Path(inventory)
        
        # Check if inventory is in the inventory directory
        inventory_path = self.inventory_path / inventory
        if inventory_path.exists():
            return inventory_path
        
        # Return the original path even if it doesn't exist
        return self.inventory_path / inventory
    
    def list_playbooks(self) -> List[str]:
        """List available playbooks
        
        Returns:
            List of playbook names
        """
        playbooks = []
        
        # Add mapped playbooks
        for name in self.playbooks.keys():
            playbooks.append(name)
        
        # Add playbooks from directory
        for path in self.playbooks_path.glob('*.yml'):
            playbooks.append(path.name)
        
        return sorted(set(playbooks))
    
    def list_inventories(self) -> List[str]:
        """List available inventories
        
        Returns:
            List of inventory names
        """
        inventories = []
        
        # Add inventories from directory
        for path in self.inventory_path.glob('*'):
            if path.is_file():
                inventories.append(path.name)
        
        return sorted(inventories)