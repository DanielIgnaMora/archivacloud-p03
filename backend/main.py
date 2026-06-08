import os
import re
import boto3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from botocore.config import Config

load_dotenv()

app = FastAPI()

# Cliente S3
s3_client = boto3.client(
    's3',
    region_name=os.getenv("AWS_REGION", "us-west-2"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    config=Config(signature_version='s3v4')
)

BUCKET_NAME = os.getenv("BUCKET_NAME", "archivacloud-p03dm")


# Modelo request
class UploadRequest(BaseModel):
    fileName: str
    fileType: str
    fileSize: int


# Sanitización
def sanitize_filename(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9.\-]', '_', filename)


# Health check
@app.get("/healthz")
def health_check():
    return {"status": "ok", "service": "ArchivaCloud P-03"}


# Endpoint principal
@app.post("/api/upload/presigned-url")
def get_presigned_url(request: UploadRequest):

    # Validaciones
    allowed_types = ["audio/mpeg", "audio/wav", "audio/x-wav"]
    allowed_extensions = [".mp3", ".wav"]

    
    ext = os.path.splitext(request.fileName.lower())[1]

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Solo MP3 o WAV"
        )

    if request.fileSize > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Máx 20MB"
        )

    if request.fileType not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Tipo MIME inválido"
        )

    # Sanitizar
    safe_name = sanitize_filename(request.fileName)
    object_key = f"uploads/{safe_name}"

    try:
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key,
                'ContentType': request.fileType
            },
            ExpiresIn=3600
        )

        return {
            "presignedUrl": url,
            "key": object_key,
            "publicUrl": f"https://{BUCKET_NAME}.s3.us-west-2.amazonaws.com/{object_key}"
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al generar la URL"
        )