# Use Python 3.10 as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CONFIG_FILE=/app/config/config.yaml \
    LOG_LEVEL=INFO

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    gnupg \
    lsb-release \
    openssh-client \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform
RUN curl -fsSL https://apt.releases.hashicorp.com/gpg | apt-key add - \
    && echo "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main" > /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update && apt-get install -y terraform \
    && rm -rf /var/lib/apt/lists/*

# Install Ansible
RUN apt-get update && apt-get install -y --no-install-recommends \
    ansible \
    sshpass \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Copy application code
COPY . .

# Create a non-root user to run the application
RUN groupadd -r chatops && useradd -r -g chatops chatops \
    && chown -R chatops:chatops /app

# Switch to non-root user
USER chatops

# Expose port for API
EXPOSE 8080

# Set entrypoint
# The bot.app module's __main__ block or ChatOpsApp class should handle whether to start
# the bot listeners or serve the API, or both. 
# If the API is meant to run alongside the bot in the same container, 
# app.py needs to manage starting Uvicorn for api.py in a separate thread/process
# or the entrypoint needs to be a script that manages both.
# For now, assuming bot.app is the main entry. If API is separate, a different CMD/ENTRYPOINT might be needed.
ENTRYPOINT ["python", "-m", "bot.app"]