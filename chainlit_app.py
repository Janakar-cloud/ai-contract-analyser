import os
import logging
import asyncio
import chainlit as cl
from chainlit.types import AskFileResponse
from chainlit.element import Element
import tempfile
import requests
import json
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
FLASK_HOST = os.environ.get("FLASK_HOST", "localhost")
FLASK_PORT = os.environ.get("FLASK_PORT", "5000")
API_BASE_URL = f"http://{FLASK_HOST}:{FLASK_PORT}"

# File upload settings
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "doc", "rtf"}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

# Helper functions
def is_allowed_file(filename: str) -> bool:
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ""

async def upload_file_to_flask(file_path: str, filename: str) -> Dict[str, Any]:
    """Upload a file to the Flask backend."""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            response = requests.post(f"{API_BASE_URL}/upload", files=files)
            
            if response.status_code == 200:
                return {"success": True, "message": "File uploaded successfully"}
            else:
                return {"success": False, "message": f"Error uploading file: {response.text}"}
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}", exc_info=True)
        return {"success": False, "message": f"Error uploading file: {str(e)}"}

async def fetch_document_status(document_id: int) -> Dict[str, Any]:
    """Fetch document processing status from Flask backend."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/document/{document_id}/status")
        if response.status_code == 200:
            return response.json()
        else:
            return {"processed": False, "job_status": "error", "error": "Failed to get status"}
    except Exception as e:
        logger.error(f"Error fetching document status: {str(e)}", exc_info=True)
        return {"processed": False, "job_status": "error", "error": str(e)}

async def fetch_document_anomalies(document_id: int) -> List[Dict[str, Any]]:
    """Fetch document anomalies from Flask backend."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/document/{document_id}/anomalies")
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except Exception as e:
        logger.error(f"Error fetching anomalies: {str(e)}", exc_info=True)
        return []

async def search_documents(query: str) -> List[Dict[str, Any]]:
    """Search documents in the backend."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/search", params={"q": query, "limit": 5})
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}", exc_info=True)
        return []

# Chainlit setup
@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session."""
    await cl.Message(
        content="""
# Welcome to Contract Anomaly Detector

This tool helps you detect anomalies in contract documents using AI-powered analysis.

## Features:
- Upload contract documents (PDF, DOCX, TXT)
- Detect date and numerical inconsistencies
- Highlight anomalous sections
- Search across your document corpus

## Getting Started:
1. Upload a document using the file icon in the chat
2. Ask questions about your documents or detected anomalies
3. Search for specific terms across all documents

Let's get started!
        """,
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    """Handle user messages."""
    message_content = message.content.strip().lower()
    
    if "upload" in message_content or "document" in message_content or "file" in message_content:
        # Guide the user to upload a file
        await cl.Message(
            content="Please upload a contract document using the file upload button in the chat. "
                   "I support PDF, DOCX, and TXT files."
        ).send()
    
    elif "search" in message_content:
        # Extract search query
        search_query = message_content.replace("search", "").strip()
        if not search_query:
            await cl.Message(content="Please provide a search term. For example: 'search payment terms'").send()
            return
            
        # Perform search
        await cl.Message(content=f"Searching for: '{search_query}'...").send()
        
        results = await search_documents(search_query)
        
        if not results:
            await cl.Message(content="No matching documents found.").send()
            return
            
        # Format search results
        result_text = "## Search Results\n\n"
        for i, doc in enumerate(results, 1):
            doc_id = doc.get("document_id")
            filename = doc.get("filename", "Unknown document")
            anomalies = doc.get("anomalies", [])
            anomaly_count = len(anomalies) if isinstance(anomalies, list) else 0
            
            result_text += f"{i}. **{filename}** (ID: {doc_id})\n"
            result_text += f"   - Anomalies detected: {anomaly_count}\n"
            
            # Display a preview of anomalies if available
            if anomaly_count > 0 and isinstance(anomalies, list):
                try:
                    # Try to parse JSON strings
                    parsed_anomalies = [json.loads(a) if isinstance(a, str) else a for a in anomalies[:2]]
                    for j, anomaly in enumerate(parsed_anomalies, 1):
                        if isinstance(anomaly, dict):
                            atype = anomaly.get("type", "unknown")
                            severity = anomaly.get("severity", "unknown")
                            desc = anomaly.get("description", "No description")
                            result_text += f"   - Anomaly {j}: {atype} ({severity}) - {desc}\n"
                except:
                    pass
            
            result_text += "\n"
            
        result_text += "\nYou can view document details by asking about a specific document ID."
        
        await cl.Message(content=result_text).send()
    
    elif message_content.startswith("document") or "show document" in message_content:
        # Try to extract document ID
        import re
        doc_id_match = re.search(r'\b(\d+)\b', message_content)
        
        if not doc_id_match:
            await cl.Message(content="Please provide a document ID. For example: 'document 1'").send()
            return
            
        doc_id = int(doc_id_match.group(1))
        
        # Fetch document status
        status = await fetch_document_status(doc_id)
        
        if not status or "error" in status:
            await cl.Message(content=f"Document {doc_id} not found or error occurred.").send()
            return
            
        # Create response based on document status
        if status.get("processed", False):
            # Fetch anomalies
            anomalies = await fetch_document_anomalies(doc_id)
            
            response = f"## Document: {status.get('filename', f'Document {doc_id}')}\n\n"
            response += f"**Status:** Processed\n"
            response += f"**Anomalies detected:** {len(anomalies)}\n\n"
            
            if anomalies:
                response += "### Detected Anomalies\n\n"
                for i, anomaly in enumerate(anomalies, 1):
                    anomaly_type = anomaly.get("type", "unknown")
                    severity = anomaly.get("severity", "unknown")
                    description = anomaly.get("description", "No description")
                    context = anomaly.get("context", "No context available")
                    
                    response += f"**{i}. {anomaly_type.capitalize()} Anomaly ({severity.upper()})**\n"
                    response += f"- {description}\n"
                    response += f"- Context: `{context[:150]}...`\n\n"
            else:
                response += "No anomalies were detected in this document."
                
            # Create link to view document in the Flask app
            doc_url = f"{API_BASE_URL}/document/{doc_id}"
            response += f"\n\n[View full document details]({doc_url})"
            
            await cl.Message(content=response).send()
        else:
            job_status = status.get("job_status", "unknown")
            await cl.Message(
                content=f"Document {doc_id} ({status.get('filename', 'Unknown')}) is not yet processed.\n"
                        f"Current status: {job_status}"
            ).send()
    
    else:
        # Generic response for other queries
        await cl.Message(
            content="I can help you with contract document anomaly detection. You can:\n\n"
                   "- Upload a document (use the file upload button)\n"
                   "- Search across documents (e.g., 'search payment terms')\n"
                   "- View document details (e.g., 'show document 1')"
        ).send()

@cl.on_file
async def on_file(file: AskFileResponse):
    """Handle file uploads."""
    # Check if file type is allowed
    if not is_allowed_file(file.name):
        await cl.Message(
            content=f"Sorry, {file.name} has an unsupported file type. "
                   f"Allowed file types are: {', '.join(ALLOWED_EXTENSIONS)}."
        ).send()
        return
    
    # Check file size
    if file.size > MAX_FILE_SIZE:
        await cl.Message(
            content=f"Sorry, {file.name} exceeds the maximum file size of 16MB."
        ).send()
        return
    
    # Save file to temporary location
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(file.content)
        temp_file_path = temp_file.name
    
    try:
        # Show processing message
        processing_msg = cl.Message(content=f"Processing {file.name}... Please wait.")
        await processing_msg.send()
        
        # Upload file to Flask backend
        upload_result = await upload_file_to_flask(temp_file_path, file.name)
        
        if upload_result.get("success", False):
            await processing_msg.update(content=f"Successfully uploaded {file.name}. The document is now being processed for anomalies.")
            
            # Create elements to display to the user
            elements = [
                Element(
                    type="file",
                    name=file.name,
                    display="inline",
                    content=file.content,
                    mime=file.mime
                )
            ]
            
            # Send confirmation with file preview
            await cl.Message(
                content=f"Document '{file.name}' has been uploaded and is being analyzed for anomalies.\n\n"
                       f"The AI is now processing the document to identify:\n"
                       f"- Date inconsistencies\n"
                       f"- Numerical value anomalies\n"
                       f"- Combined date and number anomalies\n\n"
                       f"This may take a few moments. You can ask me to 'search' for specific terms or "
                       f"check the status of your documents while you wait.",
                elements=elements
            ).send()
        else:
            await processing_msg.update(
                content=f"Error uploading {file.name}: {upload_result.get('message', 'Unknown error')}"
            )
    
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file_path)
        except:
            pass

# Run the Chainlit app
if __name__ == "__main__":
    cl.run()
