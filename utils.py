import logging
import re
from datetime import datetime, timedelta
import os
import json

logger = logging.getLogger(__name__)

def validate_date(date_str, formats=None):
    """
    Validate if a date string is valid and reasonable.
    
    Args:
        date_str (str): Date string to validate
        formats (list): List of date format strings to try
        
    Returns:
        tuple: (is_valid, parsed_date, format_used)
    """
    if formats is None:
        formats = [
            "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",  # Slash formats
            "%m-%d-%Y", "%d-%m-%Y", "%Y-%m-%d",  # Dash formats
            "%B %d, %Y", "%d %B %Y",              # Month name formats
        ]
    
    # Clean the date string
    date_str = date_str.strip()
    
    # Try each format
    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            
            # Check if date is reasonable (not in distant past or future)
            current_year = datetime.now().year
            if parsed_date.year < current_year - 100 or parsed_date.year > current_year + 50:
                continue
                
            return True, parsed_date, fmt
        
        except ValueError:
            continue
    
    return False, None, None

def extract_dates_from_text(text, patterns=None):
    """
    Extract dates from text using regex patterns.
    
    Args:
        text (str): Text to search in
        patterns (list): List of regex patterns for dates
        
    Returns:
        list: List of dictionaries with date info
    """
    if not text:
        return []
        
    if patterns is None:
        patterns = [
            r'\b\d{2}/\d{2}/\d{4}\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b\d{2}-\d{2}-\d{4}\b',  # MM-DD-YYYY or DD-MM-YYYY
            r'\b\d{4}/\d{2}/\d{2}\b',  # YYYY/MM/DD
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b',  # Month DD, YYYY
            r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',  # DD Month YYYY
        ]
    
    dates = []
    
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            date_str = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            
            # Get context (text before and after)
            context_start = max(0, start_pos - 50)
            context_end = min(len(text), end_pos + 50)
            context = text[context_start:context_end]
            
            dates.append({
                'date_str': date_str,
                'start_position': start_pos,
                'end_position': end_pos,
                'context': context
            })
    
    return dates

def extract_numbers_from_text(text, patterns=None):
    """
    Extract numbers from text using regex patterns.
    
    Args:
        text (str): Text to search in
        patterns (list): List of regex patterns for numbers
        
    Returns:
        list: List of dictionaries with number info
    """
    if not text:
        return []
        
    if patterns is None:
        patterns = [
            r'\$\s*\d+(?:,\d{3})*(?:\.\d+)?',  # Currency with $ sign
            r'€\s*\d+(?:,\d{3})*(?:\.\d+)?',   # Currency with € sign
            r'\d+(?:,\d{3})*(?:\.\d+)?\s*%',   # Percentage values
            r'\b\d+(?:,\d{3})*(?:\.\d+)?\b'    # Regular numbers
        ]
    
    numbers = []
    
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            num_str = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            
            # Clean the number for conversion
            clean_num = re.sub(r'[^\d.]', '', num_str)
            try:
                num_value = float(clean_num) if clean_num else None
            except ValueError:
                num_value = None
            
            # Get context (text before and after)
            context_start = max(0, start_pos - 50)
            context_end = min(len(text), end_pos + 50)
            context = text[context_start:context_end]
            
            numbers.append({
                'num_str': num_str,
                'num_value': num_value,
                'start_position': start_pos,
                'end_position': end_pos,
                'context': context
            })
    
    return numbers

def find_similar_sections(text, section_a, section_b, window_size=100):
    """
    Find similar sections in text.
    
    Args:
        text (str): The full text to search in
        section_a (str): First section to compare
        section_b (str): Second section to compare
        window_size (int): Size of surrounding text to capture
        
    Returns:
        tuple: (similarity_score, context_a, context_b)
    """
    from difflib import SequenceMatcher
    
    # Calculate similarity score
    similarity = SequenceMatcher(None, section_a, section_b).ratio()
    
    # Get extended context
    pos_a = text.find(section_a)
    pos_b = text.find(section_b)
    
    if pos_a >= 0 and pos_b >= 0:
        context_a = text[max(0, pos_a - window_size):min(len(text), pos_a + len(section_a) + window_size)]
        context_b = text[max(0, pos_b - window_size):min(len(text), pos_b + len(section_b) + window_size)]
    else:
        context_a = section_a
        context_b = section_b
    
    return similarity, context_a, context_b

def highlight_anomalies_in_text(text, anomalies):
    """
    Generate HTML with highlighted anomalies in text.
    
    Args:
        text (str): The full text content
        anomalies (list): List of anomaly dictionaries
        
    Returns:
        str: HTML with highlighted anomalies
    """
    if not text or not anomalies:
        return text
    
    # Sort anomalies by position (start_position) in descending order
    # to avoid position shifts when inserting HTML tags
    sorted_anomalies = sorted(
        [a for a in anomalies if a.get('start_position') is not None and a.get('end_position') is not None],
        key=lambda x: x.get('start_position', 0),
        reverse=True
    )
    
    # Insert highlight tags for each anomaly
    html_text = text
    for anomaly in sorted_anomalies:
        start_pos = anomaly.get('start_position', -1)
        end_pos = anomaly.get('end_position', -1)
        anomaly_type = anomaly.get('type', 'unknown')
        severity = anomaly.get('severity', 'medium')
        
        if start_pos >= 0 and end_pos > start_pos and end_pos <= len(html_text):
            # Get color based on severity
            if severity == 'high':
                color = 'danger'
            elif severity == 'medium':
                color = 'warning'
            else:
                color = 'info'
            
            # Create highlight span with tooltip
            tooltip_attr = f'data-toggle="tooltip" title="{anomaly_type.capitalize()} anomaly: {anomaly.get("description", "")}"'
            highlight_start = f'<span class="text-bg-{color}" {tooltip_attr}>'
            highlight_end = '</span>'
            
            # Insert tags
            html_text = html_text[:end_pos] + highlight_end + html_text[end_pos:]
            html_text = html_text[:start_pos] + highlight_start + html_text[start_pos:]
    
    return html_text

def prepare_anomaly_report(document, anomalies, text_content=None):
    """
    Generate a comprehensive anomaly report.
    
    Args:
        document (Document): Document model object
        anomalies (list): List of anomaly model objects
        text_content (str): Full text content of the document
        
    Returns:
        dict: Report data
    """
    severity_counts = {
        'high': 0,
        'medium': 0,
        'low': 0
    }
    
    type_counts = {
        'date': 0,
        'number': 0,
        'combined': 0,
        'other': 0
    }
    
    # Group and count anomalies
    for anomaly in anomalies:
        severity = anomaly.severity
        anomaly_type = anomaly.anomaly_type
        
        # Count by severity
        if severity in severity_counts:
            severity_counts[severity] += 1
        
        # Count by type
        if anomaly_type in type_counts:
            type_counts[anomaly_type] += 1
        else:
            type_counts['other'] += 1
    
    # Create report data
    report = {
        'document': {
            'id': document.id,
            'filename': document.filename,
            'upload_date': document.upload_date.strftime('%Y-%m-%d %H:%M:%S') if document.upload_date else 'Unknown',
            'file_type': document.file_type
        },
        'summary': {
            'total_anomalies': len(anomalies),
            'severity_counts': severity_counts,
            'type_counts': type_counts
        },
        'anomalies': []
    }
    
    # Add detailed anomaly information
    for anomaly in anomalies:
        report['anomalies'].append({
            'id': anomaly.id,
            'type': anomaly.anomaly_type,
            'severity': anomaly.severity,
            'description': anomaly.description,
            'context': anomaly.context,
            'start_position': anomaly.start_position,
            'end_position': anomaly.end_position,
            'detected_at': anomaly.detected_at.strftime('%Y-%m-%d %H:%M:%S') if anomaly.detected_at else 'Unknown'
        })
    
    # Add highlighted text content if available
    if text_content:
        report['highlighted_content'] = highlight_anomalies_in_text(text_content, report['anomalies'])
    
    return report

def get_mimetype(file_path):
    """
    Get mimetype of a file.
    
    Args:
        file_path (str): Path to the file
        
    Returns:
        str: Mimetype string
    """
    import mimetypes
    return mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

def create_directory_if_not_exists(directory):
    """
    Create a directory if it doesn't exist.
    
    Args:
        directory (str): Directory path
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.debug(f"Created directory: {directory}")
