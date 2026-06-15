import os
import re
import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError

# SEC-01: Carga de variables de entorno (Secretos fuera del repo) [3, 4]
load_dotenv()

app = FastAPI(title="ArchivaCloud Backend - Pareja P-03")

# SEC-02: CORS restrictivo para el puerto de Vite [3, 5]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de AWS Academy y Parámetros P-03 [2, 5]
s3_client = boto3.client(
    's3',
    region_name=os.getenv("AWS_REGION", "us-west-2"), 
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    config=Config(signature_version='s3v4')
)

BUCKET_NAME = os.getenv("BUCKET_NAME", "archivacloud-p03dm")

# SEC-03: Modelo de validación de entrada con Pydantic [6]
class UploadRequest(BaseModel):
    fileName: str = Field(..., min_length=1)
    fileType: str = Field(..., min_length=3)
    fileSize: int = Field(..., gt=0)

# SEC-03: Función de sanitización de nombre de archivo [6]
def sanitize_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9.-]', '_', name)
    return f"{clean_name}{ext.lower()}"

# Endpoint de Salud (Requisito Sprint 1) [1, 7]
@app.get("/healthz")
def health_check():
    return {
        "status": "ok", 
        "service": "ArchivaCloud P-03", 
        "region": "us-west-2",
        "bucket": BUCKET_NAME
    }

# CU-01 & CU-05: Generar Presigned URL con validaciones P-03 [1, 8]
@app.post("/api/upload/presigned-url")
def get_presigned_url(request: UploadRequest):
    # Validar tipo de archivo (P-03: MP3, WAV) [2]
    allowed_types = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp3"]
    if request.fileType.lower() not in allowed_types:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido para P-03 (Solo MP3/WAV)")

    # Validar tamaño (P-03: 20 MB = 20,971,520 bytes) [2, 3]
    max_size = 20 * 1024 * 1024
    if request.fileSize > max_size:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 20 MB")

    sanitized_name = sanitize_filename(request.fileName)
    file_key = f"uploads/{sanitized_name}"

    try:
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': file_key,
                'ContentType': request.fileType
            },
            ExpiresIn=3600
        )
        return {
            "presignedUrl": presigned_url,
            "key": file_key,
            "publicUrl": f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_key}"
        }
    except Exception:
        # SEC-07: Error sin trazas técnicas [3]
        raise HTTPException(status_code=500, detail="Error al generar la URL de subida")

# CU-02: Listar archivos (Hito Sprint 2) [1, 8, 9]
@app.get("/api/files")
def list_files():
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="uploads/")
        files = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                # Solo incluir archivos reales, no la carpeta en sí
                if obj['Key'] != "uploads/":
                    files.append({
                        "key": obj['Key'],
                        "name": obj['Key'].replace("uploads/", ""),
                        "size": obj['Size'],
                        "lastModified": obj['LastModified'].isoformat()
                    })
        return files
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo obtener la lista de archivos")

# CU-04: Eliminar archivo (Hito Sprint 2) [1, 8, 9]
@app.delete("/api/files/{key:path}")
def delete_file(key: str):
    try:
        # Verificar que el archivo existe antes de intentar borrar
        s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=key)
        return {"message": f"Archivo {key} eliminado exitosamente"}
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            raise HTTPException(status_code=404, detail="El archivo no existe en el bucket")
        raise HTTPException(status_code=500, detail="Error al eliminar el archivo")
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno al procesar la eliminación")