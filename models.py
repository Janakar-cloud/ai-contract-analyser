from datetime import datetime
from app import db

class Document(db.Model):
    """Model representing an uploaded document."""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_path = db.Column(db.String(1024), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    processed = db.Column(db.Boolean, default=False)
    weaviate_id = db.Column(db.String(255), nullable=True)
    content_length = db.Column(db.Integer, nullable=True)
    
    # Relationship with anomalies
    anomalies = db.relationship('Anomaly', backref='document', lazy=True)
    
    def __repr__(self):
        return f'<Document {self.filename}>'

class Anomaly(db.Model):
    """Model representing a detected anomaly in a document."""
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    anomaly_type = db.Column(db.String(50), nullable=False)  # date, number, combined
    severity = db.Column(db.String(20), nullable=False)  # low, medium, high
    description = db.Column(db.Text, nullable=False)
    context = db.Column(db.Text, nullable=True)  # Text surrounding the anomaly
    start_position = db.Column(db.Integer, nullable=True)  # Position in text
    end_position = db.Column(db.Integer, nullable=True)  # Position in text
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Anomaly {self.id} - {self.anomaly_type} - {self.severity}>'

class ProcessingJob(db.Model):
    """Model representing a document processing job."""
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<ProcessingJob {self.id} - {self.status}>'
