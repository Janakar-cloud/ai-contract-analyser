import os
import logging
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from datetime import datetime
from app import app, db
from models import Document, Anomaly, ProcessingJob
from processor import get_processor
from database import get_document_by_id, search_documents

logger = logging.getLogger(__name__)

# Ensure the upload directory exists
os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    allowed_extensions = app.config.get("ALLOWED_EXTENSIONS", {"pdf", "docx", "txt"})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/')
def index():
    """Render the index/home page."""
    # Get statistics for the dashboard
    stats = {
        'total_documents': Document.query.count(),
        'processed_documents': Document.query.filter_by(processed=True).count(),
        'pending_documents': Document.query.filter_by(processed=False).count(),
        'total_anomalies': Anomaly.query.count(),
        'high_severity_anomalies': Anomaly.query.filter_by(severity='high').count(),
        'medium_severity_anomalies': Anomaly.query.filter_by(severity='medium').count(),
        'low_severity_anomalies': Anomaly.query.filter_by(severity='low').count(),
    }
    
    # Get recent documents
    recent_documents = Document.query.order_by(Document.upload_date.desc()).limit(5).all()
    
    # Get recent anomalies
    recent_anomalies = Anomaly.query.order_by(Anomaly.detected_at.desc()).limit(5).all()
    
    return render_template('index.html', stats=stats, recent_documents=recent_documents, 
                          recent_anomalies=recent_anomalies)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handle document uploads."""
    if request.method == 'POST':
        # Check if a file was submitted
        if 'file' not in request.files:
            flash('No file part in the request', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('file')
        
        if not files or files[0].filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        uploaded_documents = []
        
        for file in files:
            if file and allowed_file(file.filename):
                # Secure the filename and create the file path
                filename = secure_filename(file.filename)
                file_extension = filename.rsplit('.', 1)[1].lower()
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                
                # Save the file
                file.save(file_path)
                
                # Create a database entry for the document
                document = Document(
                    filename=filename,
                    original_path=file_path,
                    file_type=file_extension,
                )
                db.session.add(document)
                db.session.commit()
                
                uploaded_documents.append(document.id)
                
                logger.info(f"Uploaded document: {filename} (ID: {document.id})")
            else:
                flash(f'File {file.filename} has an unsupported extension', 'warning')
        
        if uploaded_documents:
            # Add documents to processing queue
            processor = get_processor()
            processor.add_documents(uploaded_documents)
            
            flash(f'Successfully uploaded {len(uploaded_documents)} document(s)', 'success')
            return redirect(url_for('documents'))
        
    return render_template('upload.html')

@app.route('/documents')
def documents():
    """Display a list of all documents."""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get query parameters
    search_query = request.args.get('search', '')
    filter_processed = request.args.get('processed', '')
    
    # Base query
    query = Document.query
    
    # Apply search filter if provided
    if search_query:
        query = query.filter(Document.filename.like(f'%{search_query}%'))
    
    # Apply processed filter if provided
    if filter_processed == 'yes':
        query = query.filter_by(processed=True)
    elif filter_processed == 'no':
        query = query.filter_by(processed=False)
    
    # Order by upload date (newest first)
    query = query.order_by(Document.upload_date.desc())
    
    # Paginate results
    documents_pagination = query.paginate(page=page, per_page=per_page)
    
    return render_template('documents.html', 
                          documents=documents_pagination.items,
                          pagination=documents_pagination,
                          search_query=search_query,
                          filter_processed=filter_processed)

@app.route('/document/<int:doc_id>')
def document_view(doc_id):
    """Display a single document and its anomalies."""
    document = Document.query.get_or_404(doc_id)
    
    # Get all anomalies for this document
    anomalies = Anomaly.query.filter_by(document_id=doc_id).all()
    
    # If the document is processed, get its content from Weaviate
    document_content = None
    if document.processed and document.weaviate_id:
        weaviate_doc = get_document_by_id(doc_id, app.config)
        if weaviate_doc:
            document_content = weaviate_doc.get('content', '')
    
    # Get processing job status
    processing_job = ProcessingJob.query.filter_by(document_id=doc_id).order_by(ProcessingJob.id.desc()).first()
    
    return render_template('document_view.html',
                          document=document,
                          anomalies=anomalies,
                          document_content=document_content,
                          processing_job=processing_job)

@app.route('/anomalies')
def anomalies():
    """Display a list of all anomalies."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get query parameters
    search_query = request.args.get('search', '')
    filter_type = request.args.get('type', '')
    filter_severity = request.args.get('severity', '')
    
    # Base query with join to get document filenames
    query = Anomaly.query.join(Document, Anomaly.document_id == Document.id)
    
    # Apply search filter if provided (search in document filename)
    if search_query:
        query = query.filter(Document.filename.like(f'%{search_query}%'))
    
    # Apply type filter if provided
    if filter_type:
        query = query.filter(Anomaly.anomaly_type == filter_type)
    
    # Apply severity filter if provided
    if filter_severity:
        query = query.filter(Anomaly.severity == filter_severity)
    
    # Order by detected time (newest first)
    query = query.order_by(Anomaly.detected_at.desc())
    
    # Paginate results
    anomalies_pagination = query.paginate(page=page, per_page=per_page)
    
    return render_template('anomalies.html',
                          anomalies=anomalies_pagination.items,
                          pagination=anomalies_pagination,
                          search_query=search_query,
                          filter_type=filter_type,
                          filter_severity=filter_severity)

@app.route('/api/document/<int:doc_id>/status')
def document_status(doc_id):
    """API endpoint to check document processing status."""
    document = Document.query.get_or_404(doc_id)
    processing_job = ProcessingJob.query.filter_by(document_id=doc_id).order_by(ProcessingJob.id.desc()).first()
    
    status = {
        'document_id': doc_id,
        'filename': document.filename,
        'processed': document.processed,
        'job_status': processing_job.status if processing_job else 'unknown',
        'error': processing_job.error_message if processing_job and processing_job.error_message else None
    }
    
    return jsonify(status)

@app.route('/chainlit')
def chainlit_redirect():
    """Redirect to the ChainLit UI."""
    chainlit_url = f"http://{app.config.get('CHAINLIT_HOST', 'localhost')}:{app.config.get('CHAINLIT_PORT', 8000)}"
    return redirect(chainlit_url)

@app.route('/api/search')
def api_search():
    """API endpoint for searching documents."""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return jsonify([])
    
    results = search_documents(query, limit, app.config)
    return jsonify(results)

@app.route('/api/document/<int:doc_id>/anomalies')
def document_anomalies(doc_id):
    """API endpoint to get anomalies for a document."""
    anomalies = Anomaly.query.filter_by(document_id=doc_id).all()
    
    result = [{
        'id': a.id,
        'type': a.anomaly_type,
        'severity': a.severity,
        'description': a.description,
        'context': a.context,
        'start_position': a.start_position,
        'end_position': a.end_position,
        'detected_at': a.detected_at.isoformat() if a.detected_at else None
    } for a in anomalies]
    
    return jsonify(result)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check database connection
        Document.query.first()
        
        # Check upload directory
        upload_dir = app.config.get("UPLOAD_FOLDER", "uploads")
        if not os.path.exists(upload_dir) or not os.access(upload_dir, os.W_OK):
            return jsonify({
                'status': 'error',
                'message': 'Upload directory is not accessible',
                'timestamp': datetime.utcnow().isoformat()
            }), 500
        
        # Check processor service
        processor = get_processor()
        if not processor:
            return jsonify({
                'status': 'error',
                'message': 'Document processor is not available',
                'timestamp': datetime.utcnow().isoformat()
            }), 500
        
        # Get system status
        status = {
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': datetime.utcnow().isoformat(),
            'documents_count': Document.query.count(),
            'anomalies_count': Anomaly.query.count(),
            'database': 'connected',
            'dev_mode': app.config.get('DEV_MODE', True),
            'weaviate_enabled': app.config.get('WEAVIATE_ENABLED', False),
            'vllm_enabled': app.config.get('VLLM_ENABLED', False)
        }
        
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {str(e)}", exc_info=True)
    return render_template('500.html'), 500
