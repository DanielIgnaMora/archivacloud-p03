import os
import re
import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError

# ==============================
# CONFIG INICIAL
# ==============================
load_dotenv()

app = FastAPI(title="ArchivaCloud Backend - P-03")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REGION = os.getenv("AWS_REGION", "us-west-2")
BUCKET_NAME = os.getenv("BUCKET_NAME", "archivacloud-p03dm")
MAX_SIZE = 20 * 1024 * 1024  # 20MB

# ==============================
# CLIENTES AWS
# ==============================
s3_client = boto3.client(
    's3',
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    config=Config(signature_version='s3v4')
)

# 👉 NUEVO: DynamoDB
dynamodb = boto3.resource(
    'dynamodb',
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
)

table = dynamodb.Table('database_dynamo')

# ==============================
# MODELOS
# ==============================
class UploadRequest(BaseModel):
    fileName: str = Field(..., min_length=1)
    fileType: str = Field(..., min_length=3)
    fileSize: int = Field(..., gt=0, le=MAX_SIZE)
    fileHash: str = Field(..., min_length=64, max_length=64)

# 👉 NUEVO: modelo Dynamo
class Proyecto(BaseModel):
    id_tabla: str
    nombre_proyecto: str
    descripcion: str

# ==============================
# UTILIDADES
# ==============================
def sanitize_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9.-]', '_', name)
    return f"{clean_name}{ext.lower()}"

# ==============================
# HEALTH CHECK
# ==============================
@app.get("/healthz")
async def health_check():
    return {"status": "ok", "bucket": BUCKET_NAME}

# ==============================
# S3 - SUBIDA
# ==============================
@app.post("/api/upload/presigned-url")
async def get_presigned_url(request: UploadRequest):
    allowed_types = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp3"]

    if request.fileType.lower() not in allowed_types:
        raise HTTPException(status_code=400, detail="Solo MP3/WAV")

    clean_name = sanitize_filename(request.fileName)
    key = f"uploads/{clean_name}"

    try:
        url = s3_client.generate_presigned_url(
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

        return {"presignedUrl": url, "key": key}

    except Exception:
        raise HTTPException(status_code=500, detail="Error generando URL")

# ==============================
# S3 - LISTAR
# ==============================
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

                    download_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': BUCKET_NAME, 'Key': obj['Key']},
                        ExpiresIn=3600
                    )

                    files.append({
                        "name": obj['Key'].split('/')[-1],
                        "key": obj['Key'],
                        "size": obj['Size'],
                        "hash": file_hash,
                        "url": download_url
                    })

        return files

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error listando archivos")

# ==============================
# S3 - ELIMINAR
# ==============================
@app.delete("/api/files/{key:path}")
async def delete_file(key: str):
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=key)
        return {"message": "Archivo eliminado"}

    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            raise HTTPException(status_code=404, detail="No existe")
        raise HTTPException(status_code=500, detail="Error eliminando")

# ==============================
# 🔥 DYNAMODB - INSERTAR
# ==============================
@app.post("/api/proyectos")
async def crear_proyecto(proyecto: Proyecto):
    try:
        table.put_item(
            Item={
                'id_tabla': proyecto.id_tabla,
                'nombre_proyecto': proyecto.nombre_proyecto,
                'descripcion': proyecto.descripcion
            }
        )
        return {"message": "Proyecto guardado en DynamoDB"}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error guardando en DynamoDB")

# ==============================
# 🔥 DYNAMODB - LISTAR
# ==============================
@app.get("/api/proyectos")
async def listar_proyectos():
    try:
        response = table.scan()
        return response.get('Items', [])

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error leyendo DynamoDB")

# ==============================
# 🔥 DYNAMODB - ELIMINAR
# ==============================
@app.delete("/api/proyectos/{id_tabla}")
async def eliminar_proyecto(id_tabla: str):
    try:
        table.delete_item(
            Key={'id_tabla': id_tabla}
        )
        return {"message": "Proyecto eliminado"}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error eliminando en DynamoDB")