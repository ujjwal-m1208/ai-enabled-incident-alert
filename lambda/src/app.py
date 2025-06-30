import json
import os
import boto3
from datetime import datetime
from urllib.parse import parse_qs
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from src.endpoints import router as api_router

BEDROCK_MODEL = 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
TABLE_NAME = os.environ.get('TABLE_NAME')
API_NAME = os.environ.get('API_NAME')

# FastAPI app configuration
app = FastAPI(
    title="Twilio Incident API", 
    description="API for Twilio incident management and processing", 
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router from endpoints.py
app.include_router(api_router)

asgi_handler = Mangum(app, lifespan="off", api_gateway_base_path=API_NAME)

# SMS processing handler
def lambda_handler(event, context):
    print(event)
    if event.get('httpMethod') == 'POST' and event.get('path') == '/post-sms':
        try:
            # Extract request ID
            request_id = event.get('requestContext', {}).get('requestId')
            if not request_id:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'requestId missing in event'})
                }
            
            # Parse SMS body parameters
            body = event.get('body', '')
            params = parse_qs(body)
            description = params.get('Body', [''])[0]
            contactno = params.get('From', [''])[0]
        
            # Create prompt for AI analysis
            prompt = (
                f"Extract the following details from the incident description:\n"
                f"- Incident Location\n"
                f"- Incident Type\n"
                f"- Priority (High/Medium/Low)\n"
                f"Description: \"{description}\"\n"
                f"Respond in JSON format with keys: incident_location, incident_type, priority."
            )
            
            # Initialize services
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(TABLE_NAME)
            bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
            
            # Invoke Bedrock model
            response = bedrock.invoke_model(
                modelId=BEDROCK_MODEL,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                })
            )
        
            # Process model response
            response_body = json.loads(response['body'].read())
            model_text = response_body['content'][0]['text'].strip()
            print("Model raw response:", model_text)
    
            # Parse JSON response
            try:
                output = json.loads(model_text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Model response is not valid JSON: {e}")
                
            # Create incident record
            incident = {
                'incident_id': request_id,
                'incident_location': output.get('incident_location', 'Unknown'),
                'incident_type': output.get('incident_type', 'General'),
                'priority': output.get('priority', 'Medium'),
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'Open',
                'source': contactno,
                'original_message': description
            }
        
            # Save to DynamoDB
            table.put_item(Item=incident)
            print(json.dumps(incident, indent=2))
        
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Incident processed', 'incident': incident})
            }
        except Exception as e:
            print(f"Error processing incident: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Failed to process incident', 
                    'message': str(e)
                })
            }
    else:
        return asgi_handler(event, context)


