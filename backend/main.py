import os
import re
import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError

# SEC-01: Carga de variables de entorno (Secretos fuera del repo)
load_dotenv()

app = FastAPI(title="ArchivaCloud Backend - Pareja P-03")

# SEC-02: CORS restrictivo para el dominio del frontend (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de AWS y Parámetros P-03 [2]
REGION = os.getenv("AWS_REGION", "us-west-2")
BUCKET_NAME = os.getenv("BUCKET_NAME", "archivacloud-p03dm")
MAX_SIZE = 20 * 1024 * 1024  # 20 MB para P-03

s3_client = boto3.client(
    's3',
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    config=Config(signature_version='s3v4')
)

# SEC-03: Modelo de validación de entrada con Feature Extra [2, 3]
class UploadRequest(BaseModel):
    fileName: str = Field(..., min_length=1)
    fileType: str = Field(..., min_length=3)
    fileSize: int = Field(..., gt=0, le=MAX_SIZE) # SEC-04: Límite de tamaño
    fileHash: str = Field(..., min_length=64, max_length=64) # Hash SHA-256 (P-03)

# SEC-03: Función de sanitización de nombre de archivo [1]
def sanitize_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9.-]', '_', name)
    return f"{clean_name}{ext.lower()}"

# Endpoint de Salud (Hito Sprint 1/2) [4]
@app.get("/healthz")
async def health_check():
    return {"status": "ok", "service": "ArchivaCloud P-03", "bucket": BUCKET_NAME}

# CU-01 & CU-05: Generar Presigned URL con validaciones P-03 y Feature Extra [2, 3]
@app.post("/api/upload/presigned-url")
async def get_presigned_url(request: UploadRequest):
    # Validar tipo de archivo para P-03 (MP3, WAV) [2]
    allowed_types = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp3"]
    if request.fileType.lower() not in allowed_types:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido (Solo MP3/WAV)")

    clean_name = sanitize_filename(request.fileName)
    key = f"uploads/{clean_name}"

    try:
        # SEC-08: El archivo se guarda con metadatos de integridad (Feature Extra P-03)
        # Nota: La subida directa con metadata requiere que el frontend envíe el header x-amz-meta-sha256
        response = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': key,
                'ContentType': request.fileType,
                'Metadata': {
                    'sha256': request.fileHash  # Guardamos el hash como metadato [2]
                }
            },
            ExpiresIn=3600
        )
        return {
            "presignedUrl": response,
            "key": key
        }
    except Exception:
        # SEC-07: Errores sin trazas técnicas [1]
        raise HTTPException(status_code=500, detail="Error al generar la URL de subida")

# CU-02: Listar archivos con Hash SHA-256 (Feature Extra P-03) [2, 3]
@app.get("/api/files")
async def list_files():
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="uploads/")
        files = []

        if 'Contents' in response:
            for obj in response['Contents']:
                # Recuperar metadatos (hash) de cada objeto
                meta = s3_client.head_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                file_hash = meta.get('Metadata', {}).get('sha256', 'No disponible')

                files.append({
                    "name": obj['Key'].split('/')[-1],
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "hash": file_hash, # Feature Extra: Hash SHA-256 [2]
                    "url": f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{obj['Key']}"
                })
        return files
    except Exception:
        raise HTTPException(status_code=500, detail="Error al listar los archivos")

# CU-04: Eliminar archivo (Hito Sprint 2) [3, 4]
@app.delete("/api/files/{key:path}")
async def delete_file(key: str):
    try:
        # Verificar que el archivo existe (SEC-03) [1]
        s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=key)
        return {"message": "Archivo eliminado correctamente"}
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            raise HTTPException(status_code=404, detail="El archivo no existe")
        raise HTTPException(status_code=500, detail="Error al eliminar el archivo")