#!/usr/bin/env python3

import os
import sys
import yaml
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Import integration modules
from integrations.jenkins_integration import JenkinsIntegration
from integrations.ansible_integration import AnsibleIntegration
from integrations.terraform_integration import TerraformIntegration

class WorkflowManager:
    def __init__(self, workflow_config, integrations_config):
        self.config = workflow_config
        self.integrations_config = integrations_config
        self.templates_path = self.config.get('templates_path', 'workflows/templates')
        self.logger = logging.getLogger(__name__)
        self.jinja_env = Environment(loader=FileSystemLoader(self.templates_path))
    
    def execute(self, command: Dict[str, Any]) -> str:
        """Execute a command using the appropriate workflow
        
        Args:
            command: Command dictionary from command parser
            
        Returns:
            Result message as a string
        """
        action = command.get('action')
        parameters = command.get('parameters', {})
        workflow_name = command.get('workflow')
        
        self.logger.info(f"Executing {action} command with parameters: {parameters}")
        
        # Handle special actions directly
        if action == 'help':
            return self._handle_help(parameters.get('topic'))
        
        # Load workflow template
        workflow = self._load_workflow_template(workflow_name)
        if not workflow:
            return f"Error: Workflow template '{workflow_name}' not found"
        
        # Execute workflow
        try:
            result = self._execute_workflow(workflow, parameters)
            return result
        except Exception as e:
            self.logger.error(f"Error executing workflow: {e}")
            return f"Error executing workflow: {str(e)}"
    
    def _handle_help(self, topic: Optional[str] = None) -> str:
        """Handle help command
        
        Args:
            topic: Optional topic to get help for
            
        Returns:
            Help text as a string
        """
        if topic:
            # Show help for specific workflow
            if topic in self.default_templates:
                workflow_name = self.default_templates[topic]
                workflow = self._load_workflow_template(workflow_name)
                if workflow:
                    return self._format_workflow_help(workflow)
                else:
                    return f"No help available for workflow '{topic}'"
            else:
                return f"No help available for topic '{topic}'"
        else:
            # Show general help
            help_text = "Available workflows:\n\n"
            
            for action, workflow_name in self.default_templates.items():
                workflow = self._load_workflow_template(workflow_name)
                if workflow:
                    description = workflow.get('description', f"{action.capitalize()} workflow")
                    help_text += f"- {action.capitalize()}: {description}\n"
            
            return help_text
    
    def _format_workflow_help(self, workflow: Dict[str, Any]) -> str:
        """Format help text for a workflow
        
        Args:
            workflow: Workflow dictionary
            
        Returns:
            Formatted help text
        """
        description = workflow.get('description', 'No description available')
        steps = workflow.get('steps', [])
        
        help_text = f"Workflow: {workflow.get('name', 'Unnamed')}\n"
        help_text += f"Description: {description}\n\n"
        help_text += f"This workflow has {len(steps)} steps:\n"
        
        for i, step in enumerate(steps, 1):
            step_type = step.get('type', 'unknown')
            step_name = step.get('name', f"Step {i}")
            help_text += f"  {i}. {step_name} ({step_type})\n"
        
        return help_text
    
    def _load_workflow_template(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """Load a workflow template from file
        
        Args:
            workflow_name: Name of the workflow template file
            
        Returns:
            Workflow dictionary or None if not found
        """
        if not workflow_name:
            return None
        
        # Check if workflow template exists
        template_path = self.templates_path / workflow_name
        if not template_path.exists():
            self.logger.warning(f"Workflow template {workflow_name} not found")
            return None
        
        # Load workflow template
        try:
            with open(template_path, 'r') as f:
                workflow = yaml.safe_load(f)
            return workflow
        except Exception as e:
            self.logger.error(f"Error loading workflow template: {e}")
            return None
    
    def _execute_workflow(self, workflow: Dict[str, Any], parameters: Dict[str, Any]) -> str:
        """Execute a workflow with the given parameters
        
        Args:
            workflow: Workflow dictionary
            parameters: Command parameters
            
        Returns:
            Result message as a string
        """
        workflow_name = workflow.get('name', 'Unnamed workflow')
        steps = workflow.get('steps', [])
        
        if not steps:
            return f"Workflow '{workflow_name}' has no steps to execute"
        
        self.logger.info(f"Executing workflow '{workflow_name}' with {len(steps)} steps")
        
        # Execute each step in sequence
        results = []
        for i, step in enumerate(steps, 1):
            step_name = step.get('name', f"Step {i}")
            step_type = step.get('type', '').lower()
            step_params = step.get('parameters', {})
            
            # Replace parameter placeholders in step parameters
            step_params = self._replace_parameters(step_params, parameters)
            
            self.logger.info(f"Executing step {i}/{len(steps)}: {step_name} ({step_type})")
            
            # Execute step based on type
            try:
                if step_type == 'jenkins':
                    result = self._execute_jenkins_step(step_params)
                elif step_type == 'ansible':
                    result = self._execute_ansible_step(step_params)
                elif step_type == 'terraform':
                    result = self._execute_terraform_step(step_params)
                elif step_type == 'condition':
                    result = self._execute_condition_step(step, parameters, results)
                elif step_type == 'notification':
                    result = self._execute_notification_step(step_params)
                else:
                    result = f"Unknown step type: {step_type}"
                    self.logger.warning(result)
                
                results.append({
                    'step': i,
                    'name': step_name,
                    'type': step_type,
                    'result': result
                })
                
                # Check for step failure
                if isinstance(result, dict) and not result.get('success', True):
                    self.logger.error(f"Step {i} failed: {result.get('message', 'Unknown error')}")
                    return self._format_workflow_result(workflow_name, results)
            
            except Exception as e:
                self.logger.error(f"Error executing step {i}: {e}")
                results.append({
                    'step': i,
                    'name': step_name,
                    'type': step_type,
                    'result': {'success': False, 'message': str(e)}
                })
                return self._format_workflow_result(workflow_name, results)
        
        return self._format_workflow_result(workflow_name, results)
    
    def _replace_parameters(self, step_params: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Replace parameter placeholders in step parameters
        
        Args:
            step_params: Step parameters with placeholders
            parameters: Command parameters
            
        Returns:
            Step parameters with replaced values
        """
        result = {}
        
        for key, value in step_params.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                param_name = value[2:-1]
                if param_name in parameters:
                    result[key] = parameters[param_name]
                else:
                    result[key] = value  # Keep as is if parameter not found
            elif isinstance(value, dict):
                result[key] = self._replace_parameters(value, parameters)
            elif isinstance(value, list):
                result[key] = [self._replace_item(item, parameters) for item in value]
            else:
                result[key] = value
        
        return result
    
    def _replace_item(self, item: Any, parameters: Dict[str, Any]) -> Any:
        """Replace parameter placeholders in a single item
        
        Args:
            item: Item with potential placeholders
            parameters: Command parameters
            
        Returns:
            Item with replaced values
        """
        if isinstance(item, str) and item.startswith('${') and item.endswith('}'):
            param_name = item[2:-1]
            if param_name in parameters:
                return parameters[param_name]
        elif isinstance(item, dict):
            return self._replace_parameters(item, parameters)
        elif isinstance(item, list):
            return [self._replace_item(subitem, parameters) for subitem in item]
        
        return item
    
    def _execute_jenkins_step(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Jenkins step
        
        Args:
            params: Step parameters
            
        Returns:
            Result dictionary
        """
        job_name = params.get('job')
        job_params = params.get('parameters', {})
        wait = params.get('wait', True)
        
        if not job_name:
            return {'success': False, 'message': 'No Jenkins job specified'}
        
        return self.jenkins.trigger_job(job_name, job_params, wait)
    
    def _execute_ansible_step(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an Ansible step
        
        Args:
            params: Step parameters
            
        Returns:
            Result dictionary
        """
        playbook = params.get('playbook')
        inventory = params.get('inventory')
        extra_vars = params.get('extra_vars', {})
        
        if not playbook:
            return {'success': False, 'message': 'No Ansible playbook specified'}
        
        return self.ansible.run_playbook(playbook, inventory, extra_vars)
    
    def _execute_terraform_step(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Terraform step
        
        Args:
            params: Step parameters
            
        Returns:
            Result dictionary
        """
        action = params.get('action', 'apply')
        workspace = params.get('workspace', 'default')
        var_file = params.get('var_file')
        vars_dict = params.get('vars', {})
        
        return self.terraform.run_terraform(action, workspace, var_file, vars_dict)
    
    def _execute_condition_step(self, step: Dict[str, Any], parameters: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a condition step
        
        Args:
            step: Step dictionary
            parameters: Command parameters
            results: Results from previous steps
            
        Returns:
            Result dictionary
        """
        condition = step.get('condition', {})
        condition_type = condition.get('type', '')
        
        if condition_type == 'parameter':
            param_name = condition.get('parameter')
            param_value = condition.get('value')
            operator = condition.get('operator', 'eq')
            
            if param_name not in parameters:
                return {'success': False, 'message': f"Parameter '{param_name}' not found"}
            
            actual_value = parameters[param_name]
            result = self._evaluate_condition(actual_value, param_value, operator)
            
            if result:
                then_steps = step.get('then', [])
                if then_steps:
                    # Execute 'then' steps
                    for then_step in then_steps:
                        # Recursively execute the step
                        self._execute_workflow({'steps': [then_step]}, parameters)
                return {'success': True, 'message': 'Condition evaluated to true'}
            else:
                else_steps = step.get('else', [])
                if else_steps:
                    # Execute 'else' steps
                    for else_step in else_steps:
                        # Recursively execute the step
                        self._execute_workflow({'steps': [else_step]}, parameters)
                return {'success': True, 'message': 'Condition evaluated to false'}
        
        elif condition_type == 'result':
            step_index = condition.get('step', 1) - 1  # Convert to 0-based index
            if step_index < 0 or step_index >= len(results):
                return {'success': False, 'message': f"Step {step_index + 1} result not found"}
            
            step_result = results[step_index]['result']
            if isinstance(step_result, dict):
                success = step_result.get('success', False)
                if success:
                    then_steps = step.get('then', [])
                    if then_steps:
                        # Execute 'then' steps
                        for then_step in then_steps:
                            # Recursively execute the step
                            self._execute_workflow({'steps': [then_step]}, parameters)
                    return {'success': True, 'message': 'Condition evaluated to true'}
                else:
                    else_steps = step.get('else', [])
                    if else_steps:
                        # Execute 'else' steps
                        for else_step in else_steps:
                            # Recursively execute the step
                            self._execute_workflow({'steps': [else_step]}, parameters)
                    return {'success': True, 'message': 'Condition evaluated to false'}
        
        return {'success': False, 'message': f"Unknown condition type: {condition_type}"}
    
    def _evaluate_condition(self, actual_value: Any, expected_value: Any, operator: str) -> bool:
        """Evaluate a condition
        
        Args:
            actual_value: Actual value
            expected_value: Expected value
            operator: Comparison operator
            
        Returns:
            True if condition is met, False otherwise
        """
        if operator == 'eq':
            return actual_value == expected_value
        elif operator == 'ne':
            return actual_value != expected_value
        elif operator == 'gt':
            return actual_value > expected_value
        elif operator == 'lt':
            return actual_value < expected_value
        elif operator == 'ge':
            return actual_value >= expected_value
        elif operator == 'le':
            return actual_value <= expected_value
        elif operator == 'contains':
            return expected_value in actual_value
        elif operator == 'not_contains':
            return expected_value not in actual_value
        else:
            self.logger.warning(f"Unknown operator: {operator}")
            return False
    
    def _execute_notification_step(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a notification step
        
        Args:
            params: Step parameters
            
        Returns:
            Result dictionary
        """
        message = params.get('message', 'Notification from ChatOps')
        channel = params.get('channel')
        
        # In a real implementation, this would send a notification to the specified channel
        # For now, just log the notification
        self.logger.info(f"Notification: {message} (channel: {channel})")
        
        return {'success': True, 'message': f"Notification sent: {message}"}
    
    def _format_workflow_result(self, workflow_name: str, results: List[Dict[str, Any]]) -> str:
        """Format workflow execution results
        
        Args:
            workflow_name: Name of the workflow
            results: List of step results
            
        Returns:
            Formatted result message
        """
        # Check if all steps succeeded
        all_success = True
        for result in results:
            step_result = result['result']
            if isinstance(step_result, dict) and not step_result.get('success', True):
                all_success = False
                break
        
        # Format result message
        if all_success:
            message = f"✅ Workflow '{workflow_name}' completed successfully\n\n"
        else:
            message = f"❌ Workflow '{workflow_name}' failed\n\n"
        
        # Add step results
        message += "Steps:\n"
        for result in results:
            step_num = result['step']
            step_name = result['name']
            step_type = result['type']
            step_result = result['result']
            
            if isinstance(step_result, dict):
                success = step_result.get('success', True)
                result_message = step_result.get('message', 'No message')
                
                if success:
                    message += f"  ✅ Step {step_num}: {step_name} ({step_type}) - {result_message}\n"
                else:
                    message += f"  ❌ Step {step_num}: {step_name} ({step_type}) - {result_message}\n"
            else:
                message += f"  ✓ Step {step_num}: {step_name} ({step_type}) - {step_result}\n"
        
        return message

    def get_workflow_status(self, workflow_id: str) -> dict:
        """Retrieve the status of a given workflow ID.

        Args:
            workflow_id: The ID of the workflow to check.

        Returns:
            A dictionary containing the workflow status and details.
            Returns None if the workflow_id is not found.
        """
        # This is a placeholder implementation. 
        # In a real system, you would query a database or a job queue (like RQ)
        # to get the actual status of the workflow.
        self.logger.info(f"Fetching status for workflow_id: {workflow_id}")
        # Example: Simulating a lookup
        # from rq.job import Job
        # from redis import Redis
        # redis_conn = Redis(host=self.integrations_config.get('redis',{}).get('host','localhost'), 
        #                    port=self.integrations_config.get('redis',{}).get('port',6379))
        # try:
        #     job = Job.fetch(workflow_id, connection=redis_conn)
        #     return {
        #         "id": job.id,
        #         "status": job.get_status(),
        #         "result": job.result,
        #         "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
        #         "started_at": job.started_at.isoformat() if job.started_at else None,
        #         "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        #         "exc_info": job.exc_info
        #     }
        # except Exception as e:
        #     self.logger.error(f"Could not fetch job {workflow_id}: {e}")
        #     return None

        # Placeholder response:
        if workflow_id == "sample-workflow-123":
            return {
                "id": workflow_id,
                "status": "completed",
                "details": "Workflow completed successfully.",
                "result": {"output": "some_value"}
            }
        elif workflow_id == "sample-workflow-456":
            return {
                "id": workflow_id,
                "status": "running",
                "details": "Workflow is currently in progress.",
                "progress": "75%"
            }
        else:
            return None