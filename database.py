import logging
import weaviate
from weaviate.util import generate_uuid5
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Global Weaviate client
weaviate_client = None

def get_weaviate_client(config):
    """Initialize and return the Weaviate client."""
    global weaviate_client
    
    # Check if Weaviate is enabled
    if not config.get("WEAVIATE_ENABLED", False):
        logger.warning("Weaviate is disabled in configuration. Using development mode.")
        return None
        
    if weaviate_client is None:
        auth_config = weaviate.auth.AuthApiKey(api_key=config["WEAVIATE_API_KEY"]) if config["WEAVIATE_API_KEY"] else None
        try:
            weaviate_client = weaviate.Client(
                url=config["WEAVIATE_URL"], 
                auth_client_secret=auth_config,
                timeout_config=(5, 60)  # 5 seconds connect timeout, 60 seconds read timeout
            )
            logger.info(f"Connected to Weaviate at {config['WEAVIATE_URL']}")
            
            # Initialize schema if needed
            setup_weaviate_schema(weaviate_client, config)
        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}", exc_info=True)
            # In development mode, we'll continue without raising an exception
            if not config.get("DEV_MODE", True):
                raise
            return None
    
    return weaviate_client

def setup_weaviate_schema(client, config):
    """Set up the Weaviate schema for contract documents and anomalies."""
    class_name = config["WEAVIATE_CLASS_NAME"]
    
    # Check if class already exists
    try:
        class_exists = client.schema.exists(class_name)
        if class_exists:
            logger.debug(f"Weaviate class {class_name} already exists")
            return
        
        # Define the schema
        class_obj = {
            "class": class_name,
            "description": "A contract document with extracted text and detected anomalies",
            "vectorizer": "text2vec-transformers",
            "moduleConfig": {
                "text2vec-transformers": {
                    "vectorizeClassName": False
                }
            },
            "properties": [
                {
                    "name": "document_id",
                    "dataType": ["int"],
                    "description": "Database ID of the document"
                },
                {
                    "name": "filename",
                    "dataType": ["string"],
                    "description": "Original filename of the document"
                },
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "Full text content of the document",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "vectorizePropertyName": False,
                            "skip": False
                        }
                    }
                },
                {
                    "name": "anomalies",
                    "dataType": ["string[]"],
                    "description": "List of anomalies detected in the document"
                },
                {
                    "name": "upload_date",
                    "dataType": ["date"],
                    "description": "Date when the document was uploaded"
                }
            ]
        }
        
        # Create the class
        client.schema.create_class(class_obj)
        logger.info(f"Created Weaviate class: {class_name}")
    
    except Exception as e:
        logger.error(f"Error setting up Weaviate schema: {e}", exc_info=True)
        raise

def store_document_in_weaviate(document_id, filename, content, anomalies, config):
    """
    Store a document in Weaviate.
    
    Args:
        document_id (int): Database ID of the document
        filename (str): Original filename
        content (str): Document text content
        anomalies (list): List of detected anomalies
        config (dict): Configuration settings
        
    Returns:
        str: Weaviate object ID
    """
    # Check if Weaviate is enabled
    if not config.get("WEAVIATE_ENABLED", False):
        logger.warning(f"Weaviate is disabled. Skipping storage of document {filename} (ID: {document_id})")
        # Return a mock ID in development mode
        return f"dev-doc-{document_id}"
    
    try:
        client = get_weaviate_client(config)
        if client is None:
            logger.warning(f"Weaviate client not available. Skipping storage of document {filename} (ID: {document_id})")
            return f"dev-doc-{document_id}"
            
        class_name = config["WEAVIATE_CLASS_NAME"]
        
        # Generate deterministic UUID based on document_id
        object_id = generate_uuid5(str(document_id))
        
        # Convert anomalies to string array
        anomaly_strings = [json.dumps(a) for a in anomalies]
        
        # Prepare data object
        data_object = {
            "document_id": document_id,
            "filename": filename,
            "content": content,
            "anomalies": anomaly_strings,
            "upload_date": datetime.now().isoformat()
        }
        
        # Store in Weaviate
        client.data_object.create(
            data_object=data_object,
            class_name=class_name,
            uuid=object_id
        )
        
        logger.info(f"Stored document {filename} in Weaviate with ID {object_id}")
        return object_id
    
    except Exception as e:
        logger.error(f"Error storing document in Weaviate: {e}", exc_info=True)
        # Return a mock ID in development mode
        if config.get("DEV_MODE", True):
            return f"dev-doc-{document_id}"
        return None

def search_documents(query, limit=10, config=None):
    """
    Search for documents in Weaviate using semantic search.
    
    Args:
        query (str): Search query text
        limit (int): Maximum number of results
        config (dict): Configuration settings
        
    Returns:
        list: Search results
    """
    # Check if Weaviate is enabled
    if config and not config.get("WEAVIATE_ENABLED", False):
        logger.warning(f"Weaviate is disabled. Cannot perform semantic search for: {query}")
        return []
        
    try:
        client = get_weaviate_client(config)
        if client is None:
            logger.warning(f"Weaviate client not available. Cannot perform semantic search for: {query}")
            return []
            
        class_name = config["WEAVIATE_CLASS_NAME"]
        
        # Perform semantic search
        result = (
            client.query
            .get(class_name, ["document_id", "filename", "anomalies"])
            .with_near_text({"concepts": [query]})
            .with_limit(limit)
            .do()
        )
        
        # Extract results
        if result and "data" in result and "Get" in result["data"]:
            return result["data"]["Get"][class_name]
        return []
    
    except Exception as e:
        logger.error(f"Error searching Weaviate: {e}", exc_info=True)
        return []

def get_document_by_id(document_id, config):
    """
    Retrieve a document from Weaviate by its database ID.
    
    Args:
        document_id (int): Database ID of the document
        config (dict): Configuration settings
        
    Returns:
        dict: Document data
    """
    # Check if Weaviate is enabled
    if not config.get("WEAVIATE_ENABLED", False):
        logger.warning(f"Weaviate is disabled. Cannot retrieve document ID: {document_id}")
        return None
        
    try:
        client = get_weaviate_client(config)
        if client is None:
            logger.warning(f"Weaviate client not available. Cannot retrieve document ID: {document_id}")
            return None
            
        class_name = config["WEAVIATE_CLASS_NAME"]
        
        # Query by document_id property
        result = (
            client.query
            .get(class_name, ["document_id", "filename", "content", "anomalies", "upload_date"])
            .with_where({
                "path": ["document_id"],
                "operator": "Equal",
                "valueInt": document_id
            })
            .do()
        )
        
        # Extract result
        if result and "data" in result and "Get" in result["data"]:
            objects = result["data"]["Get"][class_name]
            if objects and len(objects) > 0:
                return objects[0]
        
        return None
    
    except Exception as e:
        logger.error(f"Error retrieving document from Weaviate: {e}", exc_info=True)
        return None
