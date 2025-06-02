// Jenkins Pipeline for Application Deployment
// This pipeline is triggered by the ChatOps bot to deploy applications

pipeline {
    agent {
        label 'deployment-agent'
    }
    
    parameters {
        string(name: 'SERVICE', defaultValue: '', description: 'The service to deploy')
        string(name: 'ENVIRONMENT', defaultValue: 'development', description: 'The environment to deploy to')
        string(name: 'VERSION', defaultValue: 'latest', description: 'The version to deploy')
        booleanParam(name: 'SKIP_TESTS', defaultValue: false, description: 'Skip running tests')
        booleanParam(name: 'NOTIFY_ON_COMPLETION', defaultValue: true, description: 'Send notification when deployment completes')
    }
    
    environment {
        DEPLOY_ID = "${params.SERVICE}-${params.ENVIRONMENT}-${params.VERSION}-${BUILD_NUMBER}"
        ANSIBLE_CONFIG = "${WORKSPACE}/ansible/ansible.cfg"
        TERRAFORM_DIR = "${WORKSPACE}/terraform/environments/${params.ENVIRONMENT}"
        ARTIFACT_REPO_CREDS = credentials('artifact-repo-credentials')
        ARTIFACT_REPO_URL = credentials('artifact-repo-url')
        NOTIFICATION_WEBHOOK = credentials('notification-webhook-url')
    }
    
    stages {
        stage('Validate Parameters') {
            steps {
                script {
                    if (params.SERVICE == '') {
                        error "SERVICE parameter is required"
                    }
                    
                    echo "Deploying ${params.SERVICE} version ${params.VERSION} to ${params.ENVIRONMENT}"
                    
                    // Log deployment start to database
                    sh """
                        curl -X POST ${env.DEPLOYMENT_TRACKER_API}/deployments \
                            -H 'Content-Type: application/json' \
                            -d '{
                                "deploy_id": "${env.DEPLOY_ID}",
                                "service": "${params.SERVICE}",
                                "environment": "${params.ENVIRONMENT}",
                                "version": "${params.VERSION}",
                                "status": "started",
                                "started_at": "'\$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"                                
                            }'
                    """
                }
            }
        }
        
        stage('Checkout') {
            steps {
                checkout scm
                
                // Update submodules if needed
                sh 'git submodule update --init --recursive'
            }
        }
        
        stage('Verify Artifact') {
            steps {
                script {
                    // Check if artifact exists in repository
                    def artifactExists = sh(script: """
                        curl -s -o /dev/null -w "%{http_code}" \
                            -u ${ARTIFACT_REPO_CREDS} \
                            ${ARTIFACT_REPO_URL}/api/v1/applications/${params.SERVICE}/versions/${params.VERSION}
                    """, returnStdout: true).trim()
                    
                    if (artifactExists != "200") {
                        error "Artifact ${params.SERVICE} version ${params.VERSION} not found in repository"
                    }
                    
                    echo "Artifact verified successfully"
                }
            }
        }
        
        stage('Pre-deployment Tests') {
            when {
                expression { return !params.SKIP_TESTS }
            }
            steps {
                script {
                    echo "Running pre-deployment tests"
                    
                    // Run tests using Ansible
                    sh """
                        cd ansible
                        ansible-playbook playbooks/pre-deploy-tests.yml \
                            -e "service_name=${params.SERVICE}" \
                            -e "environment=${params.ENVIRONMENT}" \
                            -e "version=${params.VERSION}"
                    """
                }
            }
        }
        
        stage('Backup') {
            steps {
                script {
                    echo "Creating backup before deployment"
                    
                    // Run backup using Ansible
                    sh """
                        cd ansible
                        ansible-playbook playbooks/backup.yml \
                            -e "service_name=${params.SERVICE}" \
                            -e "environment=${params.ENVIRONMENT}" \
                            -e "backup_label=pre-deploy-${env.DEPLOY_ID}"
                    """
                }
            }
        }
        
        stage('Deploy') {
            steps {
                script {
                    echo "Deploying ${params.SERVICE} version ${params.VERSION} to ${params.ENVIRONMENT}"
                    
                    // Run deployment using Ansible
                    sh """
                        cd ansible
                        ansible-playbook playbooks/deploy.yml \
                            -e "service_name=${params.SERVICE}" \
                            -e "environment=${params.ENVIRONMENT}" \
                            -e "version=${params.VERSION}"
                    """
                }
            }
        }
        
        stage('Verify Deployment') {
            steps {
                script {
                    echo "Verifying deployment"
                    
                    // Run health checks using Ansible
                    sh """
                        cd ansible
                        ansible-playbook playbooks/health-check.yml \
                            -e "service_name=${params.SERVICE}" \
                            -e "environment=${params.ENVIRONMENT}"
                    """
                }
            }
        }
        
        stage('Post-deployment Tests') {
            when {
                expression { return !params.SKIP_TESTS }
            }
            steps {
                script {
                    echo "Running post-deployment tests"
                    
                    // Run tests using Ansible
                    sh """
                        cd ansible
                        ansible-playbook playbooks/post-deploy-tests.yml \
                            -e "service_name=${params.SERVICE}" \
                            -e "environment=${params.ENVIRONMENT}" \
                            -e "version=${params.VERSION}"
                    """
                }
            }
        }
    }
    
    post {
        success {
            script {
                echo "Deployment completed successfully"
                
                // Log deployment success to database
                sh """
                    curl -X PATCH ${env.DEPLOYMENT_TRACKER_API}/deployments/${env.DEPLOY_ID} \
                        -H 'Content-Type: application/json' \
                        -d '{
                            "status": "success",
                            "completed_at": "'\$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"                            
                        }'
                """
                
                if (params.NOTIFY_ON_COMPLETION) {
                    // Send success notification
                    sh """
                        curl -X POST ${env.NOTIFICATION_WEBHOOK} \
                            -H 'Content-Type: application/json' \
                            -d '{
                                "text": "✅ Successfully deployed ${params.SERVICE} version ${params.VERSION} to ${params.ENVIRONMENT}",
                                "username": "Jenkins Deployment",
                                "icon_emoji": ":rocket:"
                            }'
                    """
                }
            }
        }
        
        failure {
            script {
                echo "Deployment failed"
                
                // Log deployment failure to database
                sh """
                    curl -X PATCH ${env.DEPLOYMENT_TRACKER_API}/deployments/${env.DEPLOY_ID} \
                        -H 'Content-Type: application/json' \
                        -d '{
                            "status": "failed",
                            "completed_at": "'\$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"                            
                        }'
                """
                
                // Send failure notification
                sh """
                    curl -X POST ${env.NOTIFICATION_WEBHOOK} \
                        -H 'Content-Type: application/json' \
                        -d '{
                            "text": "❌ Failed to deploy ${params.SERVICE} version ${params.VERSION} to ${params.ENVIRONMENT}",
                            "username": "Jenkins Deployment",
                            "icon_emoji": ":x:",
                            "attachments": [{
                                "color": "danger",
                                "title": "Build Information",
                                "title_link": "${BUILD_URL}",
                                "text": "Check the build logs for more details."
                            }]
                        }'
                """
            }
        }
        
        always {
            // Clean up workspace
            cleanWs()
        }
    }
}