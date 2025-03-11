from fastapi import APIRouter, HTTPException, Query, Depends,status
from fastapi.responses import FileResponse
import os
from typing import Optional

router = APIRouter(prefix='/download-invoice', tags=['Invoice Downloading'])

# Helper functions that need to be implemented
def validate_token(filename: str, token: str, email: str) -> bool:
    """
    Validate the security token matches the filename and email
    
    This is a placeholder - implement your actual token validation logic here.
    For example, you might:
    1. Check if the token was issued for this specific file and email
    2. Verify token hasn't expired
    3. Check if token signature is valid
    """
    # Replace with your actual validation logic
    return True  # Placeholder - always returns true

def get_invoice_path(filename: str) -> str:
    """
    Get the full path to the invoice file
    """
    # Replace with your actual path configuration
    INVOICE_DIRECTORY = os.environ.get("INVOICE_DIRECTORY", "invoices")
    return os.path.join(INVOICE_DIRECTORY, filename)

@router.get("/{filename}")
async def download_invoice(
    filename: str,
    token: str = Query(..., description="Security token"),
    email: str = Query(..., description="Customer email")
):
    """
    Download an invoice PDF file
    
    - **filename**: The invoice filename
    - **token**: Security token for verification
    - **email**: Customer email for verification
    """
    # Validate token
    if not validate_token(filename, token, email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token or email"
        )
    
    # Check if file exists
    file_path = get_invoice_path(filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Extract invoice ID for the download name
    try:
        invoice_id = filename.split('_')[1]
    except IndexError:
        invoice_id = "unknown"
    
    # Return the file
    return FileResponse(
        path=file_path,
        filename=f"Invoice_{invoice_id}.pdf",
        media_type="application/pdf"
    )