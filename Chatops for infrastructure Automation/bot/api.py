from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

from bot.app import ChatOpsApp # Assuming ChatOpsApp can be imported and instantiated

# Configure logging
logger = logging.getLogger('chatops.api')

# Initialize FastAPI app
app = FastAPI(
    title="ChatOps API",
    description="API for interacting with the ChatOps bot and triggering workflows.",
    version="1.0.0"
)

# --- CORS Middleware ---
# Allow all origins for simplicity in this example.
# For production, you should restrict this to specific origins.
origins = ["*"] # Allows all origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# --- Pydantic Models for API Requests/Responses ---
class CommandRequest(BaseModel):
    command: str
    user_id: str = "api_user"
    channel_id: str = "api_channel"

class CommandResponse(BaseModel):
    message_id: str
    status: str
    response_text: str

class WorkflowStatusRequest(BaseModel):
    workflow_id: str

class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    details: dict

# --- Dependency for ChatOpsApp ---
# This is a simplified way to get the ChatOpsApp instance.
# In a real application, you might use a more robust dependency injection system
# or ensure ChatOpsApp is a singleton accessible globally.

import os

# Global instance of ChatOpsApp for the API
chatops_app_instance: ChatOpsApp = None

def initialize_chatops_app_globally():
    global chatops_app_instance
    if chatops_app_instance is None:
        config_path = os.getenv('CONFIG_FILE', 'config/config.yaml') # Default path relative to project root
        # Ensure the path is absolute if needed, or resolve relative to a known base path
        # For Docker, '/app/config/config.yaml' will be used from ENV
        # For local dev, this might need adjustment if api.py is run from a different CWD.
        # Assuming api.py is run with WORKDIR=/app in Docker, or project root locally.
        
        # If CONFIG_FILE is relative, make it relative to the project root.
        # Project root for api.py is two levels up from bot/api.py
        if not os.path.isabs(config_path):
            project_root_api = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            config_path = os.path.join(project_root_api, config_path)

        logger.info(f"Attempting to load ChatOpsApp configuration from: {config_path}")
        try:
            # ChatOpsApp's __init__ handles loading config and setting up components.
            chatops_app_instance = ChatOpsApp(config_path=config_path)
            logger.info("ChatOpsApp instance initialized successfully for API.")
        except FileNotFoundError:
            logger.error(f"Configuration file not found at {config_path}. API cannot start.")
            # Raising an error here will prevent FastAPI from starting if config is missing.
            raise RuntimeError(f"Configuration file not found: {config_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpsApp: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize ChatOpsApp: {e}")

# Call initialization when the module is loaded, so app instance is ready for FastAPI startup.
# This ensures that get_chatops_app() will always have an instance if initialization succeeds.
# FastAPI will typically import this module, triggering this call.
initialize_chatops_app_globally()

def get_chatops_app():
    global chatops_app_instance
    if chatops_app_instance is None:
        # This state should ideally not be reached if initialize_chatops_app_globally was successful
        # or raised an error during startup.
        logger.error("ChatOpsApp instance is not available. This indicates a startup failure.")
        raise HTTPException(status_code=503, detail="ChatOps service not available due to initialization failure.")
    return chatops_app_instance


# --- API Endpoints ---

@app.post("/command", response_model=CommandResponse)
async def execute_command(request: CommandRequest, chatops: ChatOpsApp = Depends(get_chatops_app)):
    """
    Receives a command string and processes it through the ChatOps bot.
    """
    logger.info(f"Received API command: '{request.command}' from user {request.user_id}")
    try:
        # The process_message method in ChatOpsApp might need adjustment
        # to return a more structured response or handle API-specific logic.
        response_text = chatops.process_message(request.command, request.user_id, request.channel_id)
        # This is a simplified response. You might want to include a message ID for tracking.
        return CommandResponse(
            message_id="some-unique-id", # Generate or get from process_message
            status="processed",
            response_text=response_text
        )
    except Exception as e:
        logger.error(f"Error processing API command '{request.command}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflow/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str, chatops: ChatOpsApp = Depends(get_chatops_app)):
    """
    Retrieves the status of a specific workflow.
    """
    logger.info(f"Received API request for status of workflow: {workflow_id}")
    try:
        # Assuming workflow_manager has a method to get status by ID
        status_details = chatops.workflow_manager.get_workflow_status(workflow_id)
        if status_details is None:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found.")
        
        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status=status_details.get("status", "unknown"),
            details=status_details
        )
    except HTTPException:
        raise # Re-raise HTTPException to preserve status code and detail
    except Exception as e:
        logger.error(f"Error retrieving status for workflow '{workflow_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy", "message": "ChatOps API is running."}

# --- Main execution for running Uvicorn (optional, for direct execution) ---
if __name__ == "__main__":
    import uvicorn
    # The initialize_chatops_app_globally() function is called on module import,
    # so the instance should be ready or an error would have been raised.
    # We can add a check here for clarity or if running this file directly needs special handling.
    if chatops_app_instance is None:
        logger.critical("Failed to initialize ChatOpsApp. API cannot run. Check logs for errors during startup.")
        # sys.exit(1) # Or handle as appropriate
    else:
        logger.info("Starting Uvicorn for ChatOps API...")
        uvicorn.run("bot.api:app", host="0.0.0.0", port=8080, log_level="info", reload=True) # reload=True for dev
        logger.info("ChatOps API started on http://0.0.0.0:8080")