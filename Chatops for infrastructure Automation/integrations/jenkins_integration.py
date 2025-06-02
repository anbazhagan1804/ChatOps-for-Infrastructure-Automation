#!/usr/bin/env python3

import os
import time
import logging
from typing import Dict, Any, Optional, List, Union

import jenkins
from jenkins import Jenkins, JenkinsException

class JenkinsIntegration:
    """Jenkins Integration for ChatOps
    
    This class handles interactions with Jenkins CI/CD, including:
    - Triggering jobs
    - Checking build status
    - Getting build logs
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Jenkins integration with the given configuration
        
        Args:
            config: Jenkins configuration dictionary
        """
        self.logger = logging.getLogger('chatops.jenkins_integration')
        self.config = config
        
        # Initialize Jenkins client
        self.url = config.get('url')
        self.username = config.get('username')
        self.api_token = config.get('api_token')
        
        if not self.url or not self.username or not self.api_token:
            self.logger.error("Missing required Jenkins configuration")
            raise ValueError("Missing required Jenkins configuration")
        
        try:
            self.client = Jenkins(
                self.url,
                username=self.username,
                password=self.api_token
            )
            self.logger.info(f"Connected to Jenkins at {self.url}")
        except Exception as e:
            self.logger.error(f"Error connecting to Jenkins: {e}")
            self.client = None
    
    def trigger_job(self, job_name: str, parameters: Dict[str, Any] = None, wait: bool = False) -> Dict[str, Any]:
        """Trigger a Jenkins job
        
        Args:
            job_name: Name of the Jenkins job
            parameters: Job parameters
            wait: Whether to wait for job completion
            
        Returns:
            Result dictionary
        """
        if not self.client:
            return {'success': False, 'message': 'Jenkins client not initialized'}
        
        # Check if job exists
        try:
            job_info = self.client.get_job_info(job_name)
            self.logger.debug(f"Found job: {job_name}")
        except JenkinsException as e:
            self.logger.error(f"Job not found: {job_name}")
            return {'success': False, 'message': f"Job not found: {job_name}"}
        
        # Trigger job
        try:
            queue_item = self.client.build_job(job_name, parameters=parameters or {})
            self.logger.info(f"Triggered job {job_name} with parameters: {parameters}")
            
            # Wait for job to start
            build_number = None
            timeout = 30  # seconds
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                queue_info = self.client.get_queue_item(queue_item)
                if 'executable' in queue_info and 'number' in queue_info['executable']:
                    build_number = queue_info['executable']['number']
                    break
                time.sleep(1)
            
            if not build_number:
                self.logger.warning(f"Job {job_name} queued but not started within timeout")
                return {
                    'success': True,
                    'message': f"Job {job_name} queued but not started yet",
                    'queue_item': queue_item
                }
            
            self.logger.info(f"Job {job_name} started with build number {build_number}")
            
            # Wait for job completion if requested
            if wait:
                return self._wait_for_build(job_name, build_number)
            else:
                return {
                    'success': True,
                    'message': f"Job {job_name} started with build number {build_number}",
                    'build_number': build_number,
                    'build_url': f"{self.url}/job/{job_name}/{build_number}/"
                }
        
        except Exception as e:
            self.logger.error(f"Error triggering job {job_name}: {e}")
            return {'success': False, 'message': f"Error triggering job: {str(e)}"}
    
    def _wait_for_build(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Wait for a build to complete
        
        Args:
            job_name: Name of the Jenkins job
            build_number: Build number
            
        Returns:
            Result dictionary
        """
        timeout = 300  # seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                build_info = self.client.get_build_info(job_name, build_number)
                if not build_info['building']:
                    result = build_info['result']
                    self.logger.info(f"Job {job_name} #{build_number} completed with result: {result}")
                    
                    success = result == 'SUCCESS'
                    return {
                        'success': success,
                        'message': f"Job {job_name} #{build_number} completed with result: {result}",
                        'build_number': build_number,
                        'build_url': build_info['url'],
                        'result': result
                    }
                
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Error checking build status: {e}")
                time.sleep(5)
        
        self.logger.warning(f"Timeout waiting for job {job_name} #{build_number} to complete")
        return {
            'success': True,  # Not a failure, just a timeout
            'message': f"Job {job_name} #{build_number} still running (timeout reached)",
            'build_number': build_number,
            'build_url': f"{self.url}/job/{job_name}/{build_number}/",
            'result': 'UNKNOWN'
        }
    
    def get_build_status(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Get the status of a build
        
        Args:
            job_name: Name of the Jenkins job
            build_number: Build number
            
        Returns:
            Build status dictionary
        """
        if not self.client:
            return {'success': False, 'message': 'Jenkins client not initialized'}
        
        try:
            build_info = self.client.get_build_info(job_name, build_number)
            
            return {
                'success': True,
                'building': build_info['building'],
                'result': build_info['result'] if not build_info['building'] else None,
                'duration': build_info['duration'],
                'url': build_info['url'],
                'timestamp': build_info['timestamp']
            }
        except Exception as e:
            self.logger.error(f"Error getting build status: {e}")
            return {'success': False, 'message': f"Error getting build status: {str(e)}"}
    
    def get_build_log(self, job_name: str, build_number: int) -> str:
        """Get the log of a build
        
        Args:
            job_name: Name of the Jenkins job
            build_number: Build number
            
        Returns:
            Build log as a string
        """
        if not self.client:
            return "Error: Jenkins client not initialized"
        
        try:
            log = self.client.get_build_console_output(job_name, build_number)
            return log
        except Exception as e:
            self.logger.error(f"Error getting build log: {e}")
            return f"Error getting build log: {str(e)}"
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get a list of all jobs
        
        Returns:
            List of job dictionaries
        """
        if not self.client:
            return []
        
        try:
            jobs = self.client.get_jobs()
            return jobs
        except Exception as e:
            self.logger.error(f"Error getting jobs: {e}")
            return []
    
    def get_job_info(self, job_name: str) -> Dict[str, Any]:
        """Get information about a job
        
        Args:
            job_name: Name of the Jenkins job
            
        Returns:
            Job information dictionary
        """
        if not self.client:
            return {'success': False, 'message': 'Jenkins client not initialized'}
        
        try:
            job_info = self.client.get_job_info(job_name)
            return {'success': True, 'job_info': job_info}
        except Exception as e:
            self.logger.error(f"Error getting job info: {e}")
            return {'success': False, 'message': f"Error getting job info: {str(e)}"}