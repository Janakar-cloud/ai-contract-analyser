/**
 * Contract Anomaly Detector - Main JavaScript
 */

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.forEach(function(popoverTriggerEl) {
        new bootstrap.Popover(popoverTriggerEl);
    });
});

/**
 * Refresh document status periodically
 * @param {number} documentId - The ID of the document to check
 * @param {number} interval - Refresh interval in milliseconds
 */
function refreshDocumentStatus(documentId, interval = 5000) {
    const statusElement = document.getElementById('document-status');
    const statusIcon = document.getElementById('status-icon');
    const processingInfoElement = document.getElementById('processing-info');
    
    if (!statusElement || !documentId) return;
    
    // Function to update status
    const checkStatus = () => {
        fetch(`/api/document/${documentId}/status`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Update status display
                if (data.processed) {
                    statusElement.innerHTML = '<span class="badge bg-success">Processed</span>';
                    statusIcon.className = 'status-icon status-completed';
                    // Stop checking if processing is complete
                    clearInterval(statusCheckInterval);
                    // Reload the page to show results
                    window.location.reload();
                } else {
                    // Update based on job status
                    if (data.job_status === 'processing') {
                        statusElement.innerHTML = '<span class="badge bg-warning">Processing</span>';
                        statusIcon.className = 'status-icon status-processing';
                        if (processingInfoElement) {
                            processingInfoElement.classList.remove('d-none');
                        }
                    } else if (data.job_status === 'failed') {
                        statusElement.innerHTML = '<span class="badge bg-danger">Failed</span>';
                        statusIcon.className = 'status-icon status-failed';
                        clearInterval(statusCheckInterval);
                        // Show error if available
                        if (data.error && processingInfoElement) {
                            processingInfoElement.innerHTML = `<div class="alert alert-danger">
                                <h6>Processing Error</h6>
                                <p>${data.error}</p>
                            </div>`;
                            processingInfoElement.classList.remove('d-none');
                        }
                    } else if (data.job_status === 'pending') {
                        statusElement.innerHTML = '<span class="badge bg-secondary">Pending</span>';
                        statusIcon.className = 'status-icon status-pending';
                    }
                }
            })
            .catch(error => {
                console.error('Error checking document status:', error);
                statusElement.innerHTML = '<span class="badge bg-danger">Error</span>';
                clearInterval(statusCheckInterval);
            });
    };
    
    // Initial check
    checkStatus();
    
    // Set up interval for periodic checking
    const statusCheckInterval = setInterval(checkStatus, interval);
    
    // Store interval ID in the window object so it can be cleared if needed
    window.statusCheckInterval = statusCheckInterval;
    
    // Clear interval when page is unloaded
    window.addEventListener('beforeunload', function() {
        clearInterval(window.statusCheckInterval);
    });
}

/**
 * Initialize document content highlighting
 * @param {Object} anomalies - Array of anomalies with position info
 */
function initializeDocumentHighlighting(anomalies) {
    if (!anomalies || anomalies.length === 0) return;
    
    const contentElement = document.getElementById('document-content');
    if (!contentElement) return;
    
    const content = contentElement.textContent;
    let highlightedContent = content;
    
    // Get all anomalies with position info
    const positionedAnomalies = anomalies.filter(
        a => a.start_position !== null && a.end_position !== null
    );
    
    // Sort anomalies by position in reverse order (to avoid offset issues)
    positionedAnomalies.sort((a, b) => b.start_position - a.start_position);
    
    // Create highlighted content HTML
    positionedAnomalies.forEach(anomaly => {
        const start = anomaly.start_position;
        const end = anomaly.end_position;
        
        if (start >= 0 && end > start && end <= highlightedContent.length) {
            const before = highlightedContent.substring(0, start);
            const highlighted = highlightedContent.substring(start, end);
            const after = highlightedContent.substring(end);
            
            // Determine severity class
            const severityClass = anomaly.severity || 'medium';
            
            // Create tooltip attribute
            const tooltipAttr = `data-bs-toggle="tooltip" title="${anomaly.description}"`;
            
            // Apply highlighting
            highlightedContent = `${before}<span class="anomaly-highlight ${severityClass}" ${tooltipAttr}>${highlighted}</span>${after}`;
        }
    });
    
    // Update the content
    contentElement.innerHTML = highlightedContent;
    
    // Initialize tooltips
    const tooltips = new bootstrap.Tooltip(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
}

/**
 * Scroll to specific anomaly in document content
 * @param {number} anomalyId - The ID of the anomaly
 */
function scrollToAnomaly(anomalyId) {
    const anomalyElement = document.querySelector(`[data-anomaly-id="${anomalyId}"]`);
    if (!anomalyElement) return;
    
    // Scroll the anomaly into view
    anomalyElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Highlight the anomaly temporarily
    anomalyElement.classList.add('bg-secondary');
    setTimeout(() => {
        anomalyElement.classList.remove('bg-secondary');
    }, 2000);
}
