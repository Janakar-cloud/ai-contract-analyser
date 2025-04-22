import os
import logging

logger = logging.getLogger(__name__)

def load_config():
    """Load and return configuration settings."""
    config = {
        # Document Processing
        "UPLOAD_FOLDER": os.environ.get("UPLOAD_FOLDER", "/tmp/contract_uploads"),
        "ALLOWED_EXTENSIONS": {"pdf", "docx", "txt", "doc", "rtf"},
        "MAX_CONTENT_LENGTH": 16 * 1024 * 1024,  # 16 MB max file size
        
        # Development or Production mode
        "DEV_MODE": os.environ.get("DEV_MODE", "true").lower() == "true",
        
        # vLLM and Mistral Configuration
        "VLLM_ENABLED": os.environ.get("VLLM_ENABLED", "false").lower() == "true",
        "VLLM_HOST": os.environ.get("VLLM_HOST", "localhost"),
        "VLLM_PORT": int(os.environ.get("VLLM_PORT", 8000)),
        "MODEL_NAME": os.environ.get("MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2"),
        
        # Weaviate Configuration
        "WEAVIATE_ENABLED": os.environ.get("WEAVIATE_ENABLED", "false").lower() == "true",
        "WEAVIATE_URL": os.environ.get("WEAVIATE_URL", "http://localhost:8080"),
        "WEAVIATE_API_KEY": os.environ.get("WEAVIATE_API_KEY", None),
        "WEAVIATE_CLASS_NAME": "ContractDocument",
        
        # ChainLit Configuration
        "CHAINLIT_HOST": os.environ.get("CHAINLIT_HOST", "localhost"),
        "CHAINLIT_PORT": int(os.environ.get("CHAINLIT_PORT", 8000)),
        
        # Anomaly Detection Settings
        "DATE_FORMAT_PATTERNS": [
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}'
        ],
        "NUMERIC_PATTERNS": [
            r'\$\s*\d+(?:,\d{3})*(?:\.\d+)?',  # Currency with $ sign
            r'€\s*\d+(?:,\d{3})*(?:\.\d+)?',   # Currency with € sign
            r'\d+(?:,\d{3})*(?:\.\d+)?\s*%',   # Percentage values
            r'\b\d+(?:,\d{3})*(?:\.\d+)?\b'    # Regular numbers
        ],
        
        # Application Settings
        "BATCH_SIZE": int(os.environ.get("BATCH_SIZE", 5)),
        "PROCESSING_THREADS": int(os.environ.get("PROCESSING_THREADS", 2)),
    }
    
    # Create upload folder if it doesn't exist
    os.makedirs(config["UPLOAD_FOLDER"], exist_ok=True)
    logger.debug(f"Upload folder set to {config['UPLOAD_FOLDER']}")
    
    return config
