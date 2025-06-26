from fastapi.responses import JSONResponse

import uuid
import decimal
def serialize_data(obj):
    if isinstance(obj, dict):
        return {k: serialize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_data(item) for item in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    else:
        return obj
        

def success_response(data=None, message="Success"):
    """Return standardized success response"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": message,
            "data": serialize_data(data)
        }
    )

def error_response(message, status_code=400):
    """Return standardized error response"""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "message": message,
            "data": None
        }
    )