import os
import re
import uuid
import boto3
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

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

dynamodb = boto3.resource(
    'dynamodb',
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
)
dynamo_table = dynamodb.Table('database_dynamo')


# SEC-03: Modelo de validación de entrada con Feature Extra [2, 3]
class UploadRequest(BaseModel):
    fileName: str = Field(..., min_length=1)
    fileType: str = Field(..., min_length=3)
    fileSize: int = Field(..., gt=0, le=MAX_SIZE)
    fileHash: str = Field(..., min_length=64, max_length=64)


class ConfirmRequest(BaseModel):
    key: str = Field(..., min_length=1)
    fileName: str = Field(..., min_length=1)
    fileSize: int = Field(..., gt=0, le=MAX_SIZE)
    fileHash: str = Field(..., min_length=64, max_length=64)


# SEC-03: Función de sanitización de nombre de archivo [1]
def sanitize_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9.-]', '_', name)
    return f"{clean_name}{ext.lower()}"


def delete_from_dynamo_by_s3_key(s3_key: str):
    response = dynamo_table.scan(FilterExpression=Attr('s3_key').eq(s3_key))
    for item in response.get('Items', []):
        dynamo_table.delete_item(
            Key={
                'id_tabla': item['id_tabla'],
                'nombre_proyecto': item['nombre_proyecto'],
            }
        )


# Endpoint de Salud (Hito Sprint 1/2) [4]
@app.get("/healthz")
async def health_check():
    return {"status": "ok", "service": "ArchivaCloud P-03", "bucket": BUCKET_NAME}


# CU-01 & CU-05: Generar Presigned URL con validaciones P-03 y Feature Extra [2, 3]
@app.post("/api/upload/presigned-url")
async def get_presigned_url(request: UploadRequest):
    allowed_types = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp3"]
    if request.fileType.lower() not in allowed_types:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido (Solo MP3/WAV)")

    clean_name = sanitize_filename(request.fileName)
    key = f"uploads/{clean_name}"

    try:
        response = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': key,
                'ContentType': request.fileType,
                'Metadata': {
                    'sha256': request.fileHash
                }
            },
            ExpiresIn=3600
        )
        return {
            "presignedUrl": response,
            "key": key
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Error al generar la URL de subida")


# Guardar registro en DynamoDB después de subir a S3
@app.post("/api/files/confirm")
async def confirm_upload(request: ConfirmRequest):
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=request.key)
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            raise HTTPException(status_code=404, detail="El archivo no existe en S3")
        raise HTTPException(status_code=500, detail="Error al verificar el archivo en S3")
    except Exception:
        raise HTTPException(status_code=500, detail="Error al verificar el archivo en S3")

    try:
        dynamo_table.put_item(
            Item={
                'id_tabla': str(uuid.uuid4()),
                'nombre_proyecto': request.fileName,
                's3_key': request.key,
                'file_size': request.fileSize,
                'file_hash': request.fileHash,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
        )
        return {"message": "Archivo registrado en DynamoDB"}
    except Exception as e:
        print(f"Error DynamoDB: {e}")
        raise HTTPException(status_code=500, detail="Error al registrar en DynamoDB")


# CU-02: Listar archivos con Hash SHA-256 (Feature Extra P-03)
@app.get("/api/files")
async def list_files():
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="uploads/")
        files = []

        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'] != "uploads/":
                    meta = s3_client.head_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                    file_hash = meta.get('Metadata', {}).get('sha256', 'No disponible')

                    try:
                        download_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={
                                'Bucket': BUCKET_NAME,
                                'Key': obj['Key']
                            },
                            ExpiresIn=3600
                        )
                    except Exception:
                        download_url = None

                    files.append({
                        "name": obj['Key'].split('/')[-1],
                        "key": obj['Key'],
                        "size": obj['Size'],
                        "hash": file_hash,
                        "url": download_url
                    })
        return files
    except Exception as e:
        print(f"Error detectado al listar: {e}")
        raise HTTPException(status_code=500, detail="Error al listar los archivos")


# CU-04: Eliminar archivo de S3 y DynamoDB
@app.delete("/api/files/{key:path}")
async def delete_file(key: str):
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=key)
        delete_from_dynamo_by_s3_key(key)
        return {"message": "Archivo eliminado correctamente de S3 y DynamoDB"}
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            raise HTTPException(status_code=404, detail="El archivo no existe")
        raise HTTPException(status_code=500, detail="Error al eliminar el archivo")
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno al procesar la eliminación")
