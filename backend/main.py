import os
import re
import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError

# SEC-01: Carga de variables de entorno (Secretos fuera del repo) [2]
load_dotenv()

app = FastAPI(title="ArchivaCloud Backend - Pareja P-03")

# SEC-02: CORS restrictivo. IMPORTANTE: Cambia el puerto si tu frontend usa otro [2]
# No se permite "*" para cumplir con el control de seguridad.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de AWS Academy y Parámetros P-03 [3]
# Se incluye AWS_SESSION_TOKEN por ser entorno de laboratorio.
s3_client = boto3.client(
    's3',
    region_name=os.getenv("AWS_REGION", "us-west-2"), # Región obligatoria P-03
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    config=Config(signature_version='s3v4')
)

BUCKET_NAME = os.getenv("BUCKET_NAME", "archivacloud-p03dm")

# SEC-03: Modelo de validación de entrada con Pydantic [2]
class UploadRequest(BaseModel):
    fileName: str = Field(..., min_length=1)
    fileType: str = Field(..., min_length=3)
    fileSize: int = Field(..., gt=0) # Tamaño en bytes

# SEC-03: Función de sanitización de nombre de archivo [2]
def sanitize_filename(filename: str) -> str:
    # Elimina caracteres peligrosos, permite solo alfanuméricos, puntos y guiones
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9.\-]', '_', name)
    return f"{clean_name}{ext.lower()}"

# Endpoint de Salud (Requisito Sprint 1) [1]
@app.get("/healthz")
def health_check():
    return {"status": "ok", "service": "ArchivaCloud P-03", "region": "us-west-2"}

# Endpoint Principal: Generar Presigned URL [1]
@app.post("/api/upload/presigned-url")
def get_presigned_url(request: UploadRequest):
    
    # --- CU-05: Validación de Parámetros Únicos P-03 [3, 6] ---
    
    # 1. Validación de extensión (Solo MP3 y WAV)
    allowed_extensions = [".mp3", ".wav"]
    _, ext = os.path.splitext(request.fileName.lower())
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Error P-03: Extensión {ext} no permitida. Solo MP3 o WAV."
        )

    # 2. Validación de Tamaño (Máximo 20 MB)
    MAX_SIZE_MB = 20
    if request.fileSize > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400, 
            detail=f"Error P-03: El archivo supera el límite de {MAX_SIZE_MB}MB."
        )

    # 3. Validación de Tipo MIME (Protección adicional)
    allowed_mimes = ["audio/mpeg", "audio/wav", "audio/x-wav"]
    if request.fileType not in allowed_mimes:
        raise HTTPException(
            status_code=400, 
            detail="Tipo de contenido de audio no válido."
        )

    # --- SEC-03: Sanitización del Key [2] ---
    safe_name = sanitize_filename(request.fileName)
    object_key = f"uploads/{safe_name}"

    # --- Generación de la URL Firmada (Patrón Presigned URL) [7] ---
    try:
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key,
                'ContentType': request.fileType
            },
            ExpiresIn=3600 # La URL expira en 1 hora
        )

        return {
            "presignedUrl": url,
            "key": object_key,
            "publicUrl": f"https://{BUCKET_NAME}.s3.us-west-2.amazonaws.com/{object_key}"
        }

    except ClientError as e:
        # SEC-07: No exponer detalles técnicos de AWS al cliente [2]
        print(f"Error interno de AWS: {e}") # Log interno para el desarrollador
        raise HTTPException(
            status_code=500, 
            detail="Error al comunicarse con el servicio de almacenamiento."
        )
    except Exception:
        raise HTTPException(
            status_code=500, 
            detail="Ocurrió un error inesperado al procesar la subida."
        )