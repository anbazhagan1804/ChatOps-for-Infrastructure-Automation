# ChatOps for Infrastructure Automation

This project implements a ChatOps solution that allows controlling infrastructure and deployments using chat commands through Slack or Discord. It integrates with Jenkins for CI/CD, Ansible for configuration management, Terraform for infrastructure provisioning, and uses Python with NLP capabilities to parse chat messages and trigger complex workflows.

```
### Using Docker Compose

Docker Compose can be used to run the ChatOps bot and its dependencies (like Redis, Jenkins - though Jenkins in Compose is for a fresh instance, not necessarily your existing one).

1.  **Configure Environment Variables:** Create a `.env` file in the project root and define necessary variables (e.g., `SLACK_BOT_TOKEN`, `JENKINS_URL`, etc.). Refer to `docker-compose.yml` for variables used.
    Example `.env` file:
    ```env
    SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
    SLACK_APP_TOKEN=xapp-your-slack-app-token
    # DISCORD_BOT_TOKEN=your-discord-token
    JENKINS_URL=http://your-jenkins-host:port
    JENKINS_USER=your-jenkins-user
    JENKINS_API_TOKEN=your-jenkins-api-token
    CONFIG_FILE=/app/config/config.yaml 
    # For AWS/Terraform, ensure your ~/.aws credentials are set up or pass them via env vars if preferred.
    # AWS_PROFILE=default 
    ```

2.  **Build and Run:**
    ```bash
    docker-compose up --build
    ```
    To run in detached mode:
    ```bash
    docker-compose up --build -d
    ```
    The `chatops-bot` service in `docker-compose.yml` by default runs `python -m bot.app`. If you want it to run the API server by default when using Docker Compose, you would need to adjust the `command` or `entrypoint` in the `docker-compose.yml` for the `chatops-bot` service, for example:
    ```yaml
    # In docker-compose.yml, under services.chatops-bot:
    # command: ["python", "-m", "bot.app", "--serve-api"]
    ```

## Project Structure
```
├── bot/                    # Chat bot implementation (Slack/Discord)
│   ├── app.py             # Main bot application
│   ├── nlp_processor.py   # NLP processing module
│   └── command_parser.py  # Command parsing logic
├── jenkins/               # Jenkins integration
│   ├── Jenkinsfile        # Pipeline definition
│   └── scripts/           # Jenkins scripts
├── ansible/               # Ansible playbooks and roles
│   ├── playbooks/         # Task playbooks
│   └── inventory/         # Host inventories
├── terraform/             # Terraform configurations
│   ├── main.tf            # Main Terraform configuration
│   ├── variables.tf       # Variable definitions
│   └── outputs.tf         # Output definitions
├── workflows/             # Workflow definitions
│   └── templates/         # Workflow templates
├── config/                # Configuration files
│   └── config.yaml        # Main configuration
├── tests/                 # Test suite
└── requirements.txt       # Python dependencies
```

## Features

- **Chat Integration**: Connect with Slack or Discord to receive and respond to commands
- **Natural Language Processing**: Parse natural language commands to trigger appropriate actions
- **Infrastructure Management**: Control infrastructure through Terraform
- **Configuration Management**: Manage configurations with Ansible
- **CI/CD Integration**: Trigger and monitor Jenkins pipelines
- **Workflow Automation**: Define and execute complex workflows

## Setup Instructions

### Prerequisites

- Python 3.8+
- Jenkins server
- Ansible
- Terraform
- Slack or Discord account with bot creation permissions

### Installation

1. Clone this repository
2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Configure your bot tokens in `config/config.yaml`
4. Set up Jenkins, Ansible, and Terraform according to your environment
### Running the Bot

1.  **Set Environment Variables:**
    *   `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` (for Slack)
    *   `DISCORD_BOT_TOKEN` (for Discord)
    *   `JENKINS_URL`, `JENKINS_USER`, `JENKINS_API_TOKEN`
    *   `CONFIG_FILE`: Path to the configuration file (e.g., `config/config.yaml` relative to project root, or `/app/config/config.yaml` in Docker). The application defaults to `config.yaml` or `/app/config/config.yaml` if this is not set, depending on execution context.
    *   Other secrets as defined in `config.yaml` (e.g., AWS credentials, Ansible vault password file location).

2.  **Run the bot listeners:**
    ```bash
    # Ensure your current directory is the project root
    python -m bot.app --config config/config.yaml 
    ```
    (Adjust `--config` path if your `config.yaml` is elsewhere or rely on `CONFIG_FILE` env var.)

### Running the API Server

The application can also expose an HTTP API for programmatic interaction.

1.  **Set Environment Variables:** Same as for running the bot, especially `CONFIG_FILE`.

2.  **Run the API server:**
    ```bash
    # Ensure your current directory is the project root
    python -m bot.app --config config/config.yaml --serve-api
    ```
    The API will typically be available at `http://localhost:8080` (or the port configured in `config.yaml` under `app.api_port`).

### Interacting with the Web Interface (Frontend)

A simple example web interface is provided in the `frontend/` directory.

1.  **Ensure the API Server is running** (see section above).
2.  **Open `frontend/index.html` in your web browser.**
    *   You can usually do this by double-clicking the file or using "Open with..." in your file explorer.
3.  **Use the interface to send commands or check workflow status.**
    *   The frontend will make requests to `http://localhost:8080` by default. If your API is running on a different host or port, you'll need to modify the `API_BASE_URL` constant in `frontend/index.html`.

## Usage Examples

### Basic Commands

- `deploy app to production` - Deploys the application to production
- `scale service users to 5 replicas` - Scales a service
- `show status of dev environment` - Shows environment status
- `provision new test server` - Provisions a new server

### Advanced Usage

The NLP processor can understand complex commands like:

- `after deploying the api service, run the database migration and then notify the dev team`
- `if cpu usage is above 80% on production servers, scale up by 2 instances`

## Development

To extend the bot with new capabilities:

1. Add new command patterns in `bot/nlp_processor.py`
2. Create corresponding workflow templates in `workflows/templates/`
3. Implement the necessary Ansible playbooks or Terraform configurations

## License

MIT