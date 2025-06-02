#!/usr/bin/env python3

import os
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

class TerraformIntegration:
    """Terraform Integration for ChatOps
    
    This class handles interactions with Terraform for infrastructure provisioning, including:
    - Running Terraform commands (init, plan, apply, destroy)
    - Managing workspaces
    - Handling variables and outputs
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Terraform integration with the given configuration
        
        Args:
            config: Terraform configuration dictionary
        """
        self.logger = logging.getLogger('chatops.terraform_integration')
        self.config = config
        
        # Set paths from config
        self.working_dir = Path(config.get('working_dir', './terraform'))
        self.state_path = Path(config.get('state_path', './terraform/state'))
        
        # Create directories if they don't exist
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.mkdir(parents=True, exist_ok=True)
        
        # Load variable file mappings
        self.var_files = config.get('var_files', {})
        
        # Load module mappings
        self.modules = config.get('modules', [])
        
        self.logger.info(f"Terraform integration initialized with working directory {self.working_dir}")
    
    def run_terraform(self, action: str, workspace: str = 'default', var_file: Optional[str] = None, vars_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a Terraform command
        
        Args:
            action: Terraform action (init, plan, apply, destroy)
            workspace: Terraform workspace
            var_file: Variable file name or path
            vars_dict: Dictionary of variables
            
        Returns:
            Result dictionary
        """
        # Validate action
        valid_actions = ['init', 'plan', 'apply', 'destroy', 'output', 'validate', 'refresh']
        if action not in valid_actions:
            self.logger.error(f"Invalid Terraform action: {action}")
            return {'success': False, 'message': f"Invalid Terraform action: {action}"}
        
        # Resolve var file path
        var_file_path = None
        if var_file:
            var_file_path = self._resolve_var_file_path(var_file)
            if not var_file_path.exists():
                self.logger.warning(f"Variable file not found: {var_file_path}")
                var_file_path = None
        
        # Create temporary var file if vars_dict provided
        temp_var_file = None
        if vars_dict:
            try:
                temp_var_file = tempfile.NamedTemporaryFile(mode='w', suffix='.tfvars.json', delete=False)
                json.dump(vars_dict, temp_var_file)
                temp_var_file.close()
                self.logger.debug(f"Created temporary var file: {temp_var_file.name}")
            except Exception as e:
                self.logger.error(f"Error creating temporary var file: {e}")
                if temp_var_file and os.path.exists(temp_var_file.name):
                    os.unlink(temp_var_file.name)
                return {'success': False, 'message': f"Error creating temporary var file: {str(e)}"}
        
        try:
            # Initialize Terraform if needed
            if action != 'init':
                init_result = self._run_terraform_command('init', self.working_dir)
                if not init_result.get('success', False):
                    self.logger.error(f"Terraform init failed: {init_result.get('message')}")
                    return init_result
            
            # Select workspace
            if workspace != 'default':
                # Check if workspace exists
                workspace_list = self._run_terraform_command('workspace', self.working_dir, ['list'])
                if workspace not in workspace_list.get('stdout', ''):
                    # Create workspace if it doesn't exist
                    self.logger.info(f"Creating Terraform workspace: {workspace}")
                    workspace_new = self._run_terraform_command('workspace', self.working_dir, ['new', workspace])
                    if not workspace_new.get('success', False):
                        self.logger.error(f"Failed to create workspace {workspace}: {workspace_new.get('message')}")
                        return workspace_new
                else:
                    # Select existing workspace
                    self.logger.info(f"Selecting Terraform workspace: {workspace}")
                    workspace_select = self._run_terraform_command('workspace', self.working_dir, ['select', workspace])
                    if not workspace_select.get('success', False):
                        self.logger.error(f"Failed to select workspace {workspace}: {workspace_select.get('message')}")
                        return workspace_select
            
            # Prepare command arguments
            args = []
            
            # Add var file arguments
            if var_file_path:
                args.extend(['-var-file', str(var_file_path)])
            
            if temp_var_file:
                args.extend(['-var-file', temp_var_file.name])
            
            # Add auto-approve for apply and destroy
            if action in ['apply', 'destroy']:
                args.append('-auto-approve')
            
            # Run the command
            result = self._run_terraform_command(action, self.working_dir, args)
            
            # Clean up temporary var file
            if temp_var_file and os.path.exists(temp_var_file.name):
                os.unlink(temp_var_file.name)
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error running Terraform {action}: {e}")
            
            # Clean up temporary var file
            if temp_var_file and os.path.exists(temp_var_file.name):
                os.unlink(temp_var_file.name)
            
            return {'success': False, 'message': f"Error running Terraform {action}: {str(e)}"}
    
    def _run_terraform_command(self, command: str, working_dir: Path, args: List[str] = None) -> Dict[str, Any]:
        """Run a Terraform command
        
        Args:
            command: Terraform command
            working_dir: Working directory
            args: Command arguments
            
        Returns:
            Result dictionary
        """
        cmd = ['terraform', command]
        if args:
            cmd.extend(args)
        
        try:
            self.logger.info(f"Running Terraform command: {' '.join(cmd)} in {working_dir}")
            result = subprocess.run(cmd, cwd=str(working_dir), capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"Terraform {command} completed successfully")
                return {
                    'success': True,
                    'message': f"Terraform {command} completed successfully",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                self.logger.error(f"Terraform {command} failed with return code {result.returncode}")
                return {
                    'success': False,
                    'message': f"Terraform {command} failed with return code {result.returncode}",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
        
        except Exception as e:
            self.logger.error(f"Error running Terraform {command}: {e}")
            return {'success': False, 'message': f"Error running Terraform {command}: {str(e)}"}
    
    def _resolve_var_file_path(self, var_file: str) -> Path:
        """Resolve the path to a variable file
        
        Args:
            var_file: Name or path of the variable file
            
        Returns:
            Path to the variable file
        """
        # Check if var_file is a mapped name
        if var_file in self.var_files:
            var_file = self.var_files[var_file]
        
        # Check if var_file is a full path
        if os.path.isabs(var_file):
            return Path(var_file)
        
        # Check if var_file is in the working directory
        var_file_path = self.working_dir / var_file
        if var_file_path.exists():
            return var_file_path
        
        # Check if var_file needs .tfvars extension
        if not var_file.endswith('.tfvars') and not var_file.endswith('.tfvars.json'):
            var_file_with_ext = f"{var_file}.tfvars"
            var_file_path = self.working_dir / var_file_with_ext
            if var_file_path.exists():
                return var_file_path
            
            var_file_with_ext = f"{var_file}.tfvars.json"
            var_file_path = self.working_dir / var_file_with_ext
            if var_file_path.exists():
                return var_file_path
        
        # Return the original path even if it doesn't exist
        return self.working_dir / var_file
    
    def get_outputs(self, workspace: str = 'default') -> Dict[str, Any]:
        """Get Terraform outputs
        
        Args:
            workspace: Terraform workspace
            
        Returns:
            Dictionary of outputs
        """
        try:
            # Select workspace
            if workspace != 'default':
                workspace_select = self._run_terraform_command('workspace', self.working_dir, ['select', workspace])
                if not workspace_select.get('success', False):
                    self.logger.error(f"Failed to select workspace {workspace}: {workspace_select.get('message')}")
                    return {'success': False, 'message': f"Failed to select workspace {workspace}"}
            
            # Run output command
            result = self._run_terraform_command('output', self.working_dir, ['-json'])
            if not result.get('success', False):
                return {'success': False, 'message': f"Failed to get outputs: {result.get('message')}"}
            
            # Parse JSON output
            try:
                outputs = json.loads(result.get('stdout', '{}'))
                return {'success': True, 'outputs': outputs}
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing Terraform outputs: {e}")
                return {'success': False, 'message': f"Error parsing Terraform outputs: {str(e)}"}
        
        except Exception as e:
            self.logger.error(f"Error getting Terraform outputs: {e}")
            return {'success': False, 'message': f"Error getting Terraform outputs: {str(e)}"}
    
    def list_workspaces(self) -> List[str]:
        """List Terraform workspaces
        
        Returns:
            List of workspace names
        """
        try:
            result = self._run_terraform_command('workspace', self.working_dir, ['list'])
            if not result.get('success', False):
                self.logger.error(f"Failed to list workspaces: {result.get('message')}")
                return []
            
            # Parse workspace list
            workspaces = []
            for line in result.get('stdout', '').splitlines():
                workspace = line.strip().replace('*', '').strip()
                if workspace:
                    workspaces.append(workspace)
            
            return workspaces
        
        except Exception as e:
            self.logger.error(f"Error listing Terraform workspaces: {e}")
            return []
    
    def list_resources(self, workspace: str = 'default') -> List[str]:
        """List Terraform resources in the current state
        
        Args:
            workspace: Terraform workspace
            
        Returns:
            List of resource names
        """
        try:
            # Select workspace
            if workspace != 'default':
                workspace_select = self._run_terraform_command('workspace', self.working_dir, ['select', workspace])
                if not workspace_select.get('success', False):
                    self.logger.error(f"Failed to select workspace {workspace}: {workspace_select.get('message')}")
                    return []
            
            # Run state list command
            result = self._run_terraform_command('state', self.working_dir, ['list'])
            if not result.get('success', False):
                self.logger.error(f"Failed to list resources: {result.get('message')}")
                return []
            
            # Parse resource list
            resources = []
            for line in result.get('stdout', '').splitlines():
                resource = line.strip()
                if resource:
                    resources.append(resource)
            
            return resources
        
        except Exception as e:
            self.logger.error(f"Error listing Terraform resources: {e}")
            return []