import logging
import os
import uuid
from datetime import datetime
from typing import List

import boto3
from boto3.dynamodb.conditions import Attr
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from src.models import Incident, UpdateStatus

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/v1",
    tags=["incident-management"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication failed"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Server Error"}
    }
)

# Database setup
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("TABLE_NAME", "incident_alerts")  # Get table name from env var
table = dynamodb.Table(table_name)

# API endpoints
@router.get(
    "/incidents",
    response_model=List[Incident], 
    status_code=status.HTTP_200_OK,
    description="List of all available incidents with optional timestamp filtering"
)
def list_incidents(start_date: str = None, end_date: str = None):
    try:
        filter_expression = None

        if start_date and end_date:
            filter_expression = Attr('timestamp').between(start_date, end_date)
        elif start_date:
            filter_expression = Attr('timestamp').gte(start_date)
        elif end_date:
            filter_expression = Attr('timestamp').lte(end_date)
        
        if filter_expression:
            response = table.scan(
                FilterExpression=filter_expression
            )
        else:
            # If no dates provided, return all incidents
            response = table.scan()
            
        items = response.get("Items", [])
        return items
    except Exception as e:
        logger.error(f"Error retrieving incidents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Unexpected error: {str(e)}"
        )



@router.get(
    "/incidents/{incident_id}",
    response_model=Incident,
    status_code=status.HTTP_200_OK,
    description="Retrieve a specific incident report using its unique incident_id"
)
def get_incident(incident_id: str):
    try:
        response = table.get_item(Key={"incident_id": incident_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with ID '{incident_id}' not found"
            )
        return item
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch incident: {str(e)}"
        )


@router.delete("/incidents/{incident_id}", status_code=status.HTTP_200_OK)
def delete_incident(incident_id: str):
    # Check if the item exists
    response = table.get_item(Key={"incident_id": incident_id})
    item = response.get("Item")

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    # Delete the item
    table.delete_item(Key={"incident_id": incident_id})
    return {"message": f"Incident {incident_id} deleted successfully"}


@router.put("/update-status", status_code=status.HTTP_200_OK)
def update_status(status_data: UpdateStatus):
    # Check if incident exists
    incident_id = status_data.incident_id
    response = table.get_item(Key={"incident_id": incident_id})
    if "Item" not in response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Incident with ID '{incident_id}' not found"
        )

    # Update status
    table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": status_data.status},
    )

    return {"message": f"Incident {incident_id} status updated to {status_data.status}"}


@router.post(
    "/create_incident",
    response_model=Incident,
    status_code=status.HTTP_201_CREATED,
    description="Create a new incident"
)
def create_incident(incident: Incident):
    try:
        # Generate unique ID if not provided
        if not incident.incident_id:
            incident.incident_id = str(uuid.uuid4())
            
        # Set timestamp if not provided
        if not incident.timestamp:
            incident.timestamp = datetime.utcnow().isoformat()
            
        # Convert to dict and save to DynamoDB
        incident_dict = incident.dict()
        table.put_item(Item=incident_dict)
        
        return incident_dict
    except Exception as e:
        logger.error(f"Error creating incident: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create incident: {str(e)}"
        )


