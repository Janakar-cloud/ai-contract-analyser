import re
import logging
from datetime import datetime
import requests
import json

logger = logging.getLogger(__name__)

def detect_anomalies(text, config):
    """
    Detect anomalies in the contract text using Mistral 7B through vLLM.
    
    Args:
        text (str): The text content of the document
        config (dict): Configuration settings
        
    Returns:
        list: List of anomalies detected
    """
    if not text:
        logger.warning("Empty text provided for anomaly detection")
        return []
    
    logger.debug("Starting anomaly detection process")
    
    anomalies = []
    
    # First, perform rule-based detection for simple cases
    rule_based_anomalies = detect_rule_based_anomalies(text, config)
    anomalies.extend(rule_based_anomalies)
    
    # Then, perform AI-based detection using Mistral 7B
    ai_based_anomalies = detect_ai_based_anomalies(text, config)
    anomalies.extend(ai_based_anomalies)
    
    logger.info(f"Detected {len(anomalies)} anomalies in total")
    
    return anomalies

def detect_rule_based_anomalies(text, config):
    """
    Detect anomalies using rule-based patterns.
    
    Args:
        text (str): The text content of the document
        config (dict): Configuration settings
        
    Returns:
        list: List of anomalies detected using rules
    """
    anomalies = []
    
    # Date pattern anomalies
    date_patterns = config["DATE_FORMAT_PATTERNS"]
    dates = []
    
    for pattern in date_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            date_str = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            context = text[max(0, start_pos - 50):min(len(text), end_pos + 50)]
            
            # Extract surrounding text for context
            dates.append({
                "date_str": date_str,
                "start_position": start_pos,
                "end_position": end_pos,
                "context": context
            })
    
    # Check for date inconsistencies
    if len(dates) > 1:
        # Sort dates by position in text
        dates.sort(key=lambda x: x["start_position"])
        
        # Check for potential date anomalies
        for i in range(len(dates) - 1):
            current_date = dates[i]["date_str"]
            next_date = dates[i+1]["date_str"]
            
            # Simple heuristic: if dates are close together but different formats
            # Consider it a potential anomaly
            if dates[i+1]["start_position"] - dates[i]["end_position"] < 200:
                # Different formats close to each other might be suspicious
                if (current_date.count('/') and next_date.count('-')) or \
                   (current_date.count('-') and next_date.count('/')):
                    anomalies.append({
                        'type': 'date',
                        'severity': 'medium',
                        'description': f'Inconsistent date formats: {current_date} and {next_date}',
                        'context': f"...{dates[i]['context']}... and ...{dates[i+1]['context']}...",
                        'start_position': dates[i]["start_position"],
                        'end_position': dates[i+1]["end_position"]
                    })
    
    # Numeric pattern anomalies
    numeric_patterns = config["NUMERIC_PATTERNS"]
    numbers = []
    
    for pattern in numeric_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            num_str = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            context = text[max(0, start_pos - 50):min(len(text), end_pos + 50)]
            
            # Clean the number for comparison
            clean_num = re.sub(r'[^\d.]', '', num_str)
            if clean_num:
                try:
                    num_value = float(clean_num)
                    numbers.append({
                        "num_str": num_str,
                        "num_value": num_value,
                        "start_position": start_pos,
                        "end_position": end_pos,
                        "context": context
                    })
                except ValueError:
                    pass  # Skip if conversion fails
    
    # Check for numeric anomalies
    if len(numbers) > 1:
        # Sort numbers by position in text
        numbers.sort(key=lambda x: x["start_position"])
        
        # Check for potential numeric anomalies (large discrepancies)
        for i in range(len(numbers) - 1):
            # If numbers are close in text but significantly different in value
            if numbers[i+1]["start_position"] - numbers[i]["end_position"] < 200:
                ratio = max(numbers[i]["num_value"], numbers[i+1]["num_value"]) / (
                    min(numbers[i]["num_value"], numbers[i+1]["num_value"]) or 1)
                
                if ratio > 10 and min(numbers[i]["num_value"], numbers[i+1]["num_value"]) > 1:
                    anomalies.append({
                        'type': 'number',
                        'severity': 'high',
                        'description': f'Significant numeric discrepancy: {numbers[i]["num_str"]} and {numbers[i+1]["num_str"]}',
                        'context': f"...{numbers[i]['context']}... and ...{numbers[i+1]['context']}...",
                        'start_position': numbers[i]["start_position"],
                        'end_position': numbers[i+1]["end_position"]
                    })
    
    logger.debug(f"Detected {len(anomalies)} rule-based anomalies")
    return anomalies

def detect_ai_based_anomalies(text, config):
    """
    Detect anomalies using Mistral 7B served by vLLM.
    
    Args:
        text (str): The text content of the document
        config (dict): Configuration settings
        
    Returns:
        list: List of anomalies detected using AI
    """
    anomalies = []
    
    # Check if vLLM service is enabled
    vllm_enabled = config.get("VLLM_ENABLED", False)
    if not vllm_enabled:
        logger.warning("vLLM is not enabled in configuration. Skipping AI-based anomaly detection.")
        # Return a development mode placeholder anomaly
        anomalies.append({
            'type': 'combined',
            'severity': 'medium',
            'description': 'Development mode: vLLM/Mistral 7B service not available. This is a placeholder anomaly.',
            'context': 'This anomaly was generated in development mode as vLLM/Mistral 7B was not available. Configure the VLLM_ENABLED setting to use AI-based detection.',
            'start_position': 0,
            'end_position': min(100, len(text)) if text else 0
        })
        return anomalies
    
    # If text is too long, split it into chunks
    max_chunk_size = 8000  # Limit chunk size for model input
    chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
    
    logger.debug(f"Split document into {len(chunks)} chunks for AI analysis")
    
    vllm_url = f"http://{config['VLLM_HOST']}:{config['VLLM_PORT']}/generate"
    
    for i, chunk in enumerate(chunks):
        # Skip very small chunks
        if len(chunk) < 100:
            continue
            
        prompt = f"""
You are an AI specialized in legal document analysis. Carefully examine the following contract text for anomalies, focusing specifically on:

1. Date inconsistencies or unusual dates
2. Numerical value anomalies (amounts, percentages, etc.)
3. Combined date and number anomalies (e.g., payment deadlines vs. amounts)

For each anomaly, provide:
- Type (date, number, or combined)
- Severity (low, medium, high)
- Description of the anomaly
- The exact text containing the anomaly

Format your response as a JSON array of objects, each with keys: "type", "severity", "description", "context".

Contract text:
{chunk}

Return ONLY the JSON array. If no anomalies are found, return an empty JSON array [].
"""

        try:
            # Call the vLLM API to get Mistral 7B response
            payload = {
                "prompt": prompt,
                "temperature": 0.3,
                "max_tokens": 1000,
                "stop": None
            }
            
            response = requests.post(vllm_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("text", "")
                
                # Extract JSON array from the response
                try:
                    # Find JSON array in the response
                    json_start = generated_text.find('[')
                    json_end = generated_text.rfind(']') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = generated_text[json_start:json_end]
                        chunk_anomalies = json.loads(json_str)
                        
                        # Add offset to any positions if we're processing chunks
                        chunk_offset = i * max_chunk_size
                        for anomaly in chunk_anomalies:
                            # Add chunk offset to the anomaly position if it exists
                            if 'start_position' in anomaly:
                                anomaly['start_position'] += chunk_offset
                            if 'end_position' in anomaly:
                                anomaly['end_position'] += chunk_offset
                                
                            anomalies.append(anomaly)
                    else:
                        logger.warning(f"No valid JSON found in response for chunk {i}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from model response: {e}")
                    logger.debug(f"Raw response: {generated_text}")
            else:
                logger.error(f"vLLM API request failed with status code {response.status_code}")
                logger.debug(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Error during AI anomaly detection: {str(e)}", exc_info=True)
            # Add a fallback anomaly when the service is unavailable
            anomalies.append({
                'type': 'combined',
                'severity': 'low',
                'description': f'Error connecting to vLLM/Mistral 7B service: {str(e)}',
                'context': 'There was an error connecting to the AI service. This is a placeholder anomaly.',
                'start_position': 0,
                'end_position': min(100, len(text)) if text else 0
            })
    
    logger.debug(f"Detected {len(anomalies)} AI-based anomalies")
    return anomalies
