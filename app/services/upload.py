import os
import tempfile
from fastapi import UploadFile, HTTPException
from ..config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, BUCKET_NAME
from b2sdk.v2 import B2Api, InMemoryAccountInfo

async def upload_image(file: UploadFile, bucket_name: str = BUCKET_NAME):
    # Validate the file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are allowed.")
    
    try:
        # Create a temporary file to store the image content
        with tempfile.NamedTemporaryFile(delete=False, mode='wb') as temp_file:
            # Read the file content as binary and write it to the temp file
            content = await file.read()  # Use await to properly read the content asynchronously
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Authorize Backblaze account with B2Api
        application_key_id = AWS_ACCESS_KEY_ID
        application_key = AWS_SECRET_ACCESS_KEY
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", application_key_id, application_key)
        
        # Get the bucket from Backblaze
        bucket = b2_api.get_bucket_by_name(bucket_name)

        # Upload the image to Backblaze
        uploaded_file = bucket.upload_local_file(local_file=temp_file_path, file_name=file.filename)

        # Retrieve the URL of the uploaded file
        image_url = b2_api.get_download_url_for_fileid(uploaded_file.id_)

        # Clean up the temporary file after upload
        os.remove(temp_file_path)
        
        # Return the image URL
        return image_url

    except Exception as e:
        # Handle any errors that occur during the upload process
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")
