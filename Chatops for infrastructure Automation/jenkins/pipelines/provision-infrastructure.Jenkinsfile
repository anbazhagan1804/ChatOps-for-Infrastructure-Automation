// Jenkins Pipeline for Infrastructure Provisioning
// This pipeline is triggered by the ChatOps bot to provision infrastructure

pipeline {
    agent {
        label 'infrastructure-agent'
    }
    
    parameters {
        string(name: 'RESOURCE_TYPE', defaultValue: '', description: 'The type of resource to provision')
        string(name: 'ENVIRONMENT', defaultValue: 'development', description: 'The environment to provision in')
        string(name: 'COUNT', defaultValue: '1', description: 'The number of resources to provision')
        string(name: 'REGION', defaultValue: 'us-east-1', description: 'The region to provision in')
        booleanParam(name: 'SKIP_VALIDATION', defaultValue: false, description: 'Skip validation steps')
        booleanParam(name: 'NOTIFY_ON_COMPLETION', defaultValue: true, description: 'Send notification when provisioning completes')
    }
    
    environment {
        PROVISION_ID = "${params.RESOURCE_TYPE}-${params.ENVIRONMENT}-${BUILD_NUMBER}"
        TERRAFORM_DIR = "${WORKSPACE}/terraform/environments/${params.ENVIRONMENT}"
        ANSIBLE_CONFIG = "${WORKSPACE}/ansible/ansible.cfg"
        NOTIFICATION_WEBHOOK = credentials('notification-webhook-url')
        AWS_CREDENTIALS = credentials('aws-credentials')
        TERRAFORM_STATE_BACKEND_CONFIG = credentials('terraform-backend-config')
    }
    
    stages {
        stage('Validate Parameters') {
            steps {
                script {
                    if (params.RESOURCE_TYPE == '') {
                        error "RESOURCE_TYPE parameter is required"
                    }
                    
                    echo "Provisioning ${params.COUNT} ${params.RESOURCE_TYPE}(s) in ${params.ENVIRONMENT} (${params.REGION})"
                    
                    // Log provisioning start to database
                    sh """
                        curl -X POST ${env.INFRASTRUCTURE_TRACKER_API}/provisions \
                            -H 'Content-Type: application/json' \
                            -d '{
                                "provision_id": "${env.PROVISION_ID}",
                                "resource_type": "${params.RESOURCE_TYPE}",
                                "environment": "${params.ENVIRONMENT}",
                                "count": ${params.COUNT},
                                "region": "${params.REGION}",
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
        
        stage('Validate Infrastructure Code') {
            when {
                expression { return !params.SKIP_VALIDATION }
            }
            steps {
                script {
                    echo "Validating Terraform code"
                    
                    // Run Terraform validation
                    sh """
                        cd ${TERRAFORM_DIR}
                        terraform init -backend-config=${TERRAFORM_STATE_BACKEND_CONFIG}
                        terraform validate
                    """
                }
            }
        }
        
        stage('Terraform Plan') {
            steps {
                script {
                    echo "Creating Terraform plan"
                    
                    // Run Terraform plan
                    sh """
                        cd ${TERRAFORM_DIR}
                        terraform init -backend-config=${TERRAFORM_STATE_BACKEND_CONFIG}
                        terraform workspace select ${params.ENVIRONMENT} || terraform workspace new ${params.ENVIRONMENT}
                        terraform plan \
                            -var="resource_type=${params.RESOURCE_TYPE}" \
                            -var="resource_count=${params.COUNT}" \
                            -var="region=${params.REGION}" \
                            -var="environment=${params.ENVIRONMENT}" \
                            -out=tfplan
                    """
                }
            }
        }
        
        stage('Approval') {
            when {
                expression { return params.ENVIRONMENT == 'production' }
            }
            steps {
                // Require manual approval for production environment
                input message: "Do you want to apply the Terraform plan to PRODUCTION?", ok: "Apply"
            }
        }
        
        stage('Terraform Apply') {
            steps {
                script {
                    echo "Applying Terraform plan"
                    
                    // Run Terraform apply
                    sh """
                        cd ${TERRAFORM_DIR}
                        terraform apply -auto-approve tfplan
                    """
                }
            }
        }
        
        stage('Get Terraform Outputs') {
            steps {
                script {
                    echo "Getting Terraform outputs"
                    
                    // Get Terraform outputs
                    def tfOutput = sh(script: """
                        cd ${TERRAFORM_DIR}
                        terraform output -json
                    """, returnStdout: true).trim()
                    
                    // Parse JSON output
                    def outputs = readJSON text: tfOutput
                    
                    // Save outputs for later use
                    env.RESOURCE_IDS = outputs.resource_ids.value.join(',')
                    env.RESOURCE_IPS = outputs.resource_ips.value.join(',')
                }
            }
        }
        
        stage('Update Inventory') {
            steps {
                script {
                    echo "Updating Ansible inventory"
                    
                    // Run Ansible playbook to update inventory
                    sh """
                        cd ansible
                        ansible-playbook playbooks/update-inventory.yml \
                            -e "resource_type=${params.RESOURCE_TYPE}" \
                            -e "environment=${params.ENVIRONMENT}" \
                            -e "resource_ids=${env.RESOURCE_IDS}" \
                            -e "resource_ips=${env.RESOURCE_IPS}"
                    """
                }
            }
        }
        
        stage('Configure Resources') {
            steps {
                script {
                    echo "Configuring new resources"
                    
                    // Run Ansible playbook to configure resources
                    sh """
                        cd ansible
                        ansible-playbook playbooks/configure.yml \
                            -e "resource_type=${params.RESOURCE_TYPE}" \
                            -e "environment=${params.ENVIRONMENT}"
                    """
                }
            }
        }
        
        stage('Validate Resources') {
            when {
                expression { return !params.SKIP_VALIDATION }
            }
            steps {
                script {
                    echo "Validating provisioned resources"
                    
                    // Run Ansible playbook to validate resources
                    sh """
                        cd ansible
                        ansible-playbook playbooks/validate-resources.yml \
                            -e "resource_type=${params.RESOURCE_TYPE}" \
                            -e "environment=${params.ENVIRONMENT}"
                    """
                }
            }
        }
    }
    
    post {
        success {
            script {
                echo "Provisioning completed successfully"
                
                // Log provisioning success to database
                sh """
                    curl -X PATCH ${env.INFRASTRUCTURE_TRACKER_API}/provisions/${env.PROVISION_ID} \
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
                                "text": "✅ Successfully provisioned ${params.COUNT} ${params.RESOURCE_TYPE}(s) in ${params.ENVIRONMENT} (${params.REGION})",
                                "username": "Jenkins Infrastructure",
                                "icon_emoji": ":cloud:",
                                "attachments": [{
                                    "color": "good",
                                    "fields": [
                                        {
                                            "title": "Resource IDs",
                                            "value": "${env.RESOURCE_IDS}",
                                            "short": false
                                        }
                                    ]
                                }]
                            }'
                    """
                }
            }
        }
        
        failure {
            script {
                echo "Provisioning failed"
                
                // Log provisioning failure to database
                sh """
                    curl -X PATCH ${env.INFRASTRUCTURE_TRACKER_API}/provisions/${env.PROVISION_ID} \
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
                            "text": "❌ Failed to provision ${params.COUNT} ${params.RESOURCE_TYPE}(s) in ${params.ENVIRONMENT} (${params.REGION})",
                            "username": "Jenkins Infrastructure",
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