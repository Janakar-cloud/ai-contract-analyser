# Contract Anomaly Detection System

An AI-powered contract anomaly detection system designed to identify and analyze potential risks in contract documents. This application leverages Mistral 7B, vLLM, and Weaviate for advanced anomaly detection in contract documents.

## Overview

This system analyzes uploaded contracts to identify anomalies in dates, numbers, and logical inconsistencies. It provides a comprehensive web interface for managing documents and a conversational interface through ChainLit for interactive queries.

## Key Features

- **Document Management**: Upload and manage contract documents (PDF, DOCX, TXT)
- **AI-Powered Anomaly Detection**: Identify potential risks using both rule-based and AI techniques
- **Severity Classification**: Anomalies classified by severity (low, medium, high)
- **Contextual Analysis**: View anomalies in the context of the surrounding text
- **Vector Search**: Search across documents using semantic similarity
- **Interactive UI**: Both traditional web interface and conversational ChainLit UI
- **Development Mode**: Operate without external AI services for testing/development
- **Flexible Deployment**: Local WSL Ubuntu deployment with Docker

## System Architecture

- **Flask Application**: Web interface and API endpoints
- **ChainLit Interface**: Conversational UI for document interaction
- **Weaviate Vector Database**: Document storage and semantic search
- **Mistral 7B via vLLM**: AI model for detecting complex anomalies
- **PostgreSQL/SQLite**: Relational database for document metadata
- **Redis**: Caching and task queue for improved performance
- **Nginx**: Reverse proxy for load balancing and static file serving

## Quick Start (Automated Setup)

The easiest way to get started is to use the provided setup script:

```bash
# Make the script executable
chmod +x setup-and-run.sh

# Run the setup script
./setup-and-run.sh
```

The script will:
1. Check for Docker and other prerequisites
2. Let you choose between development mode (no AI services) or full mode
3. Set up the environment and configuration files
4. Build and start the necessary Docker containers
5. Provide access information for the application

## Manual Installation

### Prerequisites

- WSL Ubuntu or native Ubuntu/Debian system
- Docker and Docker Compose
- At least 8GB RAM and 10GB free disk space for full mode
- 4GB RAM for development mode

### Step 1: Environment Configuration

Create a `.env` file from the template:

```bash
cp .env-example .env
```

Edit the `.env` file to configure:
- Database connection details
- AI service endpoints
- Application settings

### Step 2: Building the Application

```bash
# Build the Docker images
make build
```

### Step 3: Running the Application

#### Development Mode (No AI Services)

```bash
# Start in development mode
make up

# Access web interface at http://localhost
# Access ChainLit UI at http://localhost:8000
```

#### Production Mode (With AI Services)

```bash
# Start in production mode with all services
make prod

# Access web interface at http://localhost
# Access ChainLit UI at http://localhost:8000
```

### Step 4: Managing the Application

```bash
# View application logs
make logs

# Access shell in app container
make shell

# Stop all services
make down

# View application status
make status

# Completely remove application and data
make clean
```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | Database connection string | sqlite:////data/contract_anomaly.db |
| UPLOAD_FOLDER | Document upload directory | /data/uploads |
| DEV_MODE | Run in development mode | true |
| VLLM_ENABLED | Enable vLLM integration | false |
| WEAVIATE_ENABLED | Enable Weaviate integration | false |
| VLLM_HOST | vLLM service hostname | vllm |
| VLLM_PORT | vLLM service port | 8000 |
| WEAVIATE_URL | Weaviate service URL | http://weaviate:8080 |
| SESSION_SECRET | Secret key for session | randomly generated |

### Using External AI Services

If you have existing vLLM or Weaviate services, you can configure the application to use them by editing the `.env` file:

```
# External vLLM service
VLLM_ENABLED=true
VLLM_HOST=your-vllm-host
VLLM_PORT=8000

# External Weaviate service
WEAVIATE_ENABLED=true
WEAVIATE_URL=http://your-weaviate-host:8080
WEAVIATE_API_KEY=your-api-key-if-needed
```

## Health Monitoring

The application includes health check endpoints to monitor system status:

- `/health` - Returns service health information
- `/api/document/<id>/status` - Check document processing status

## Docker Services Overview

| Service | Description | Port |
|---------|-------------|------|
| app | Main Flask application | 5000 |
| chainlit | ChainLit UI interface | 8000 |
| nginx | Web server/reverse proxy | 80 |
| postgres | PostgreSQL database | 5432 |
| redis | Redis for caching | 6379 |
| weaviate | Vector database | 8080 |
| t2v-transformers | Transformer models for embeddings | internal |

## Development and Customization

### Adding New Anomaly Detection Rules

Extend the rule-based detection in `anomaly_detector.py`:

```python
def detect_rule_based_anomalies(text, config):
    anomalies = []
    
    # Add your custom detection rules here
    # Example: Detect suspicious date ranges
    suspicious_dates = detect_suspicious_date_ranges(text)
    for date in suspicious_dates:
        anomalies.append({
            'type': 'date',
            'severity': 'medium',
            'description': 'Suspicious date range detected',
            'context': date['context'],
            'start_position': date['start'],
            'end_position': date['end']
        })
    
    return anomalies
```

### Modifying the AI Detection Prompt

The AI detection can be customized by modifying the prompt template in `anomaly_detector.py`:

```python
def detect_ai_based_anomalies(text, config):
    # Customize the prompt for the AI model
    prompt = f"""You are a legal expert analyzing a contract document.
    Identify and explain any anomalies, inconsistencies, or potential issues in the following text:

    {text}

    Pay special attention to:
    1. Inconsistent dates or suspiciously distant future dates
    2. Unusual or inconsistent monetary values
    3. Contradictory clauses or statements
    4. Vague or ambiguous terms with legal implications
    
    Format your response as a JSON array of anomalies with these fields:
    - type: The category of anomaly (date, number, logical, language)
    - severity: How serious the issue is (low, medium, high)
    - description: Brief explanation of the issue
    - context: The text surrounding the anomaly
    """
    
    # Send to vLLM service and process response
    # ...
```

## Troubleshooting

### Common Issues

- **Application fails to start**: Check Docker logs with `docker-compose logs app`
- **Document upload fails**: Ensure the upload directory exists and has proper permissions
- **AI services unavailable**: Verify vLLM and Weaviate are running with `docker-compose ps`
- **Database connection errors**: Check database credentials and connectivity
- **500 Internal Server Errors**: Check application logs for detailed error messages

### Debugging

Enable debug logging by setting `FLASK_DEBUG=1` in the environment variables.

### Resource Constraints

If you encounter memory issues when running in full mode:

1. Reduce the resource limits in `docker-compose.yml`
2. Consider using external AI services instead of running them locally
3. Run in development mode which requires fewer resources

## Security Considerations

- Generate a strong `SESSION_SECRET` for production use
- Use secure passwords for PostgreSQL in production
- Consider adding authentication for the web interface
- Review and restrict container network access
- Use HTTPS in production environments

## License

This project is licensed under the MIT License - see the LICENSE file for details.
