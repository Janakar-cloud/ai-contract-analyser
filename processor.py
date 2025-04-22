import os
import threading
import logging
from datetime import datetime
from app import db, app
from models import Document, ProcessingJob, Anomaly
from document_parser import parse_document
from anomaly_detector import detect_anomalies
from database import store_document_in_weaviate

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Handles the document processing pipeline."""
    
    def __init__(self, config):
        self.config = config
        self.processing_queue = []
        self.processing_lock = threading.Lock()
        self.max_threads = config["PROCESSING_THREADS"]
        self.active_threads = 0
    
    def add_document(self, document_id):
        """Add a document to the processing queue."""
        with self.processing_lock:
            # Create a processing job entry
            job = ProcessingJob(document_id=document_id, status='pending')
            db.session.add(job)
            db.session.commit()
            
            self.processing_queue.append((document_id, job.id))
            logger.debug(f"Added document {document_id} to processing queue")
            
            # Start processing if threads are available
            self._process_queue()
    
    def add_documents(self, document_ids):
        """Add multiple documents to the processing queue."""
        for doc_id in document_ids:
            self.add_document(doc_id)
    
    def _process_queue(self):
        """Process documents in the queue if threads are available."""
        with self.processing_lock:
            # Check if we can start new processing threads
            while self.processing_queue and self.active_threads < self.max_threads:
                doc_id, job_id = self.processing_queue.pop(0)
                self.active_threads += 1
                
                # Start processing in a new thread
                thread = threading.Thread(
                    target=self._process_document,
                    args=(doc_id, job_id),
                    daemon=True
                )
                thread.start()
                logger.debug(f"Started processing thread for document {doc_id}")
    
    def _process_document(self, document_id, job_id):
        """Process a single document through the entire pipeline."""
        try:
            with app.app_context():
                # Update job status
                job = ProcessingJob.query.get(job_id)
                job.status = 'processing'
                job.start_time = datetime.utcnow()
                db.session.commit()
                
                # Get document
                document = Document.query.get(document_id)
                if not document:
                    raise ValueError(f"Document with ID {document_id} not found")
                
                logger.info(f"Processing document: {document.filename}")
                
                # Step 1: Parse the document to extract text
                text_content = parse_document(document.original_path, document.file_type)
                document.content_length = len(text_content) if text_content else 0
                
                # Step 2: Detect anomalies
                anomalies = detect_anomalies(text_content, self.config)
                
                # Step 3: Store anomalies in the database
                for anomaly_data in anomalies:
                    anomaly = Anomaly(
                        document_id=document_id,
                        anomaly_type=anomaly_data['type'],
                        severity=anomaly_data['severity'],
                        description=anomaly_data['description'],
                        context=anomaly_data.get('context'),
                        start_position=anomaly_data.get('start_position'),
                        end_position=anomaly_data.get('end_position')
                    )
                    db.session.add(anomaly)
                
                # Step 4: Store the document in Weaviate
                weaviate_id = store_document_in_weaviate(
                    document_id, 
                    document.filename, 
                    text_content, 
                    anomalies,
                    self.config
                )
                document.weaviate_id = weaviate_id
                
                # Mark document as processed
                document.processed = True
                
                # Update job as completed
                job.status = 'completed'
                job.end_time = datetime.utcnow()
                db.session.commit()
                
                logger.info(f"Document {document.filename} processed successfully")
                
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}", exc_info=True)
            
            with app.app_context():
                # Update job status
                job = ProcessingJob.query.get(job_id)
                if job:
                    job.status = 'failed'
                    job.error_message = str(e)
                    job.end_time = datetime.utcnow()
                    db.session.commit()
        
        finally:
            # Decrease active thread count and process next document if available
            with self.processing_lock:
                self.active_threads -= 1
                self._process_queue()

# Initialize the document processor with the app context
document_processor = None

def get_processor():
    """Get or initialize the document processor."""
    global document_processor
    if document_processor is None:
        with app.app_context():
            document_processor = DocumentProcessor(app.config)
    return document_processor
