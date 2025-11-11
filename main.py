from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import anthropic
import os
from datetime import datetime
from dotenv import load_dotenv
import PyPDF2
import io
import json
import time
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

# ===================== Token de entorno =====================
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise RuntimeError("API_TOKEN no configurado en entorno.")

security = HTTPBearer(auto_error=False)


def verify_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header Authorization: Bearer <token>",
        )
    if credentials.scheme.lower() != "bearer" or credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o no autorizado",
        )
    return True

# ===================== Inicialización =====================
app = FastAPI(
    title="AI Document Processor API",
    description="Procesa PDFs, facturas y CVs automáticamente con IA - By Jorge Lago",
    version="1.0.0"
)
ALLOWED_ORIGINS = [
    "https://automapymes.com",
    "https://www.automapymes.com",
    "https://*.automapymes.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== Rate limiting =====================
RATE_LIMIT = int(os.getenv("RATE_LIMIT", 30))  # peticiones por minuto
RATE_WINDOW = 60  # segundos
request_timestamps: dict[str, list[float]] = {}

def check_rate_limit(client_ip: str):
    now = time.time()
    timestamps = request_timestamps.get(client_ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(timestamps) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas peticiones. Espera un minuto antes de volver a intentar."
        )
    timestamps.append(now)
    request_timestamps[client_ip] = timestamps

# ===================== Modelos =====================
class ProcessResponse(BaseModel):
    document_type: str
    extracted_data: Dict[str, Any]
    raw_text_preview: str
    tokens_used: int
    timestamp: str
    confidence: str

# ===================== Prompts =====================
EXTRACTION_PROMPTS = {
    "invoice": """Analiza esta factura y extrae la siguiente información en formato JSON:
{
  "numero_factura": "string",
  "fecha": "YYYY-MM-DD",
  "proveedor": {"nombre": "string","cif": "string","direccion": "string"},
  "cliente": {"nombre": "string","cif": "string"},
  "lineas": [{"concepto": "string","cantidad": number,"precio_unitario": number,"total": number}],
  "subtotal": number,"iva": number,"total": number
}
Devuelve SOLO el JSON.""",

    "cv": """Analiza este CV y extrae la siguiente información en formato JSON:
{
  "datos_personales": {"nombre": "string","email": "string","telefono": "string","linkedin": "string","ubicacion": "string"},
  "resumen_profesional": "string",
  "experiencia": [{"puesto": "string","empresa": "string","periodo": "string","descripcion": "string"}],
  "educacion": [{"titulo": "string","institucion": "string","fecha": "string"}],
  "habilidades": ["string"],
  "idiomas": [{"idioma": "string","nivel": "string"}],
  "puntuacion_match": {"experiencia_años": number,"nivel_tecnico": "junior/mid/senior","areas_destacadas": ["string"]}
}
Devuelve SOLO el JSON.""",

    "generic": """Analiza este documento y extrae la información más relevante en JSON.
Incluye tipo de documento, fechas, nombres, cantidades y conceptos principales."""
}

# ===================== Utilidades =====================
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = "".join(page.extract_text() + "\n" for page in pdf_reader.pages)
        return text.strip()
    except Exception:
        raise HTTPException(status_code=400, detail="Error al leer PDF.")

def process_with_ai(text: str, document_type: str) -> tuple[Dict[str, Any], int]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Error interno")

    client = anthropic.Anthropic(api_key=api_key)
    extraction_prompt = EXTRACTION_PROMPTS.get(document_type, EXTRACTION_PROMPTS["generic"])

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            temperature=0.2,
            messages=[{"role": "user", "content": f"{extraction_prompt}\n\nTexto:\n{text[:4000]}"}]
        )
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        response_text = response.content[0].text

        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        extracted_data = json.loads(response_text.strip())
        return extracted_data, tokens_used
    except json.JSONDecodeError:
        return {"raw_response": "Formato no válido"}, tokens_used
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno")

# ===================== Rutas =====================
@app.get("/")
def root():
    return {
        "message": "AI Document Processor API - Activa",
        "docs": "/docs",
        "version": "1.0.0",
        "supported_types": ["invoice", "cv", "generic"],
        "developer": "Jorge Lago Campos"
    }

@app.post("/process/pdf", response_model=ProcessResponse, dependencies=[Depends(verify_bearer_token)])
async def process_pdf(
    file: UploadFile = File(...),
    document_type: str = Form(default="generic"),
    req: Request = None
):
    client_ip = "unknown"
    if req:
        forwarded = req.headers.get("x-forwarded-for")
        client_ip = (forwarded or (req.client.host if req.client else "unknown")).split(",")[0]
    check_rate_limit(client_ip)

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    if document_type not in EXTRACTION_PROMPTS:
        raise HTTPException(status_code=400, detail=f"Tipo no válido. Usa: {list(EXTRACTION_PROMPTS.keys())}")

    file_bytes = await file.read()
    text = extract_text_from_pdf(file_bytes)
    if not text or len(text) < 50:
        raise HTTPException(status_code=400, detail="PDF vacío o ilegible.")

    extracted_data, tokens_used = process_with_ai(text, document_type)
    confidence = "high" if len(str(extracted_data)) > 200 else "medium"

    return ProcessResponse(
        document_type=document_type,
        extracted_data=extracted_data,
        raw_text_preview=text[:500] + "..." if len(text) > 500 else text,
        tokens_used=tokens_used,
        timestamp=datetime.now().isoformat(),
        confidence=confidence
    )

@app.post("/process/text", dependencies=[Depends(verify_bearer_token)])
async def process_text(text: str = Form(...), document_type: str = Form(default="generic"), req: Request = None):
    client_ip = "unknown"
    if req:
        forwarded = req.headers.get("x-forwarded-for")
        client_ip = (forwarded or (req.client.host if req.client else "unknown")).split(",")[0]
    check_rate_limit(client_ip)

    if len(text) < 50:
        raise HTTPException(status_code=400, detail="Texto demasiado corto")

    extracted_data, tokens_used = process_with_ai(text, document_type)
    return {
        "document_type": document_type,
        "extracted_data": extracted_data,
        "tokens_used": tokens_used,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/templates", dependencies=[Depends(verify_bearer_token)])
def get_templates(req: Request = None):
    if req:
        forwarded = req.headers.get("x-forwarded-for")
        client_ip = (forwarded or (req.client.host if req.client else "unknown")).split(",")[0]
        check_rate_limit(client_ip)
    return {
        "available_types": list(EXTRACTION_PROMPTS.keys()),
        "templates": {k: v[:200] + "..." for k, v in EXTRACTION_PROMPTS.items()}
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ===================== Middleware =====================
@app.middleware("http")
async def block_token_in_query(request: Request, call_next):
    if "token" in request.query_params:
        return JSONResponse(status_code=401, content={"detail": "No autorizado"})
    return await call_next(request)

# ===================== OpenAPI sin Auth =====================
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Eliminar solo definiciones de seguridad, no los schemas
    if "components" in schema:
        schema["components"].pop("securitySchemes", None)
    schema.pop("security", None)

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

# ===================== Main =====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
