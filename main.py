from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import anthropic
import os
from datetime import datetime
from dotenv import load_dotenv
import PyPDF2
import io
import json
import time

load_dotenv()

app = FastAPI(
    title="AI Document Processor API",
    description="Procesa PDFs, facturas y CVs automáticamente con IA - By Jorge Lago",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Auth por Bearer ==============
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

API_TOKEN = os.getenv("API_TOKEN")
security = HTTPBearer(auto_error=False)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header Authorization: Bearer <token>"
        )
    if credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o no autorizado"
        )
    return True

# ============== Rate limiting por IP =========
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

# Modelos de respuesta
class ProcessResponse(BaseModel):
    document_type: str
    extracted_data: Dict[str, Any]
    raw_text_preview: str
    tokens_used: int
    timestamp: str
    confidence: str

# Plantillas de extracción por tipo de documento
EXTRACTION_PROMPTS = {
    "invoice": """Analiza esta factura y extrae la siguiente información en formato JSON:
{
  "numero_factura": "string",
  "fecha": "YYYY-MM-DD",
  "proveedor": {
    "nombre": "string",
    "cif": "string",
    "direccion": "string"
  },
  "cliente": {
    "nombre": "string",
    "cif": "string"
  },
  "lineas": [
    {
      "concepto": "string",
      "cantidad": number,
      "precio_unitario": number,
      "total": number
    }
  ],
  "subtotal": number,
  "iva": number,
  "total": number
}

Devuelve SOLO el JSON, sin explicaciones adicionales.""",

    "cv": """Analiza este CV y extrae la siguiente información en formato JSON:
{
  "datos_personales": {
    "nombre": "string",
    "email": "string",
    "telefono": "string",
    "linkedin": "string",
    "ubicacion": "string"
  },
  "resumen_profesional": "string",
  "experiencia": [
    {
      "puesto": "string",
      "empresa": "string",
      "periodo": "string",
      "descripcion": "string"
    }
  ],
  "educacion": [
    {
      "titulo": "string",
      "institucion": "string",
      "fecha": "string"
    }
  ],
  "habilidades": ["string"],
  "idiomas": [
    {
      "idioma": "string",
      "nivel": "string"
    }
  ],
  "puntuacion_match": {
    "experiencia_años": number,
    "nivel_tecnico": "junior/mid/senior",
    "areas_destacadas": ["string"]
  }
}

Devuelve SOLO el JSON, sin explicaciones adicionales.""",

    "generic": """Analiza este documento y extrae la información más relevante de forma estructurada en JSON.
Identifica: tipo de documento, fechas clave, nombres, cantidades, conceptos principales.
Devuelve un JSON con la estructura que mejor se adapte al contenido."""
}

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrae texto de un PDF"""
    try:
        pdf_file = io.BytesIO(file_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer PDF: {str(e)}")

def process_with_ai(text: str, document_type: str) -> tuple[Dict[str, Any], int]:
    """Procesa el texto con Claude y extrae datos estructurados"""
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key no configurada")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Seleccionar prompt según tipo
    extraction_prompt = EXTRACTION_PROMPTS.get(document_type, EXTRACTION_PROMPTS["generic"])
    
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            temperature=0.2,  # Más bajo para mayor precisión
            messages=[
                {
                    "role": "user",
                    "content": f"{extraction_prompt}\n\nTexto del documento:\n\n{text[:4000]}"  # Limitar a primeros 4000 chars
                }
            ]
        )
        
        # Parsear JSON de la respuesta
        response_text = response.content[0].text
        
        # Intentar extraer JSON si viene con markdown
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        extracted_data = json.loads(response_text.strip())
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        
        return extracted_data, tokens_used
        
    except json.JSONDecodeError:
        # Si falla el parsing, devolver texto plano
        return {"raw_response": response_text, "warning": "No se pudo parsear como JSON"}, tokens_used
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en procesamiento IA: {str(e)}")

@app.get("/")
def root():
    return {
        "message": "AI Document Processor API - Activa",
        "docs": "/docs",
        "version": "1.0.0",
        "supported_types": ["invoice", "cv", "generic"],
        "developer": "Jorge Lago Campos"
    }

@app.post("/process/pdf", response_model=ProcessResponse, dependencies=[Depends(verify_token)])
async def process_pdf(
    file: UploadFile = File(...),
    document_type: str = Form(default="generic", description="Tipo: invoice, cv, generic"),
    req: Request = None
):
    # Rate limit por IP
    check_rate_limit(req.client.host if req and req.client else "unknown")

    """
    Procesa un PDF y extrae datos estructurados.
    
    - **file**: Archivo PDF a procesar
    - **document_type**: Tipo de documento (invoice, cv, generic)
    """
    
    # Validar tipo de archivo
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    # Validar tipo de documento
    if document_type not in EXTRACTION_PROMPTS:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo no válido. Usa: {list(EXTRACTION_PROMPTS.keys())}"
        )
    
    try:
        # Leer archivo
        file_bytes = await file.read()
        
        # Extraer texto
        text = extract_text_from_pdf(file_bytes)
        
        if not text or len(text) < 50:
            raise HTTPException(
                status_code=400, 
                detail="PDF vacío o no se pudo extraer texto. Asegúrate que no sea una imagen escaneada."
            )
        
        # Procesar con IA
        extracted_data, tokens_used = process_with_ai(text, document_type)
        
        # Determinar confianza basado en completitud de datos
        confidence = "high" if len(str(extracted_data)) > 200 else "medium"
        
        return ProcessResponse(
            document_type=document_type,
            extracted_data=extracted_data,
            raw_text_preview=text[:500] + "..." if len(text) > 500 else text,
            tokens_used=tokens_used,
            timestamp=datetime.now().isoformat(),
            confidence=confidence
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(e)}")

@app.post("/process/text", dependencies=[Depends(verify_token)])
async def process_text(
    text: str = Form(...),
    document_type: str = Form(default="generic"),
    req: Request = None
):
    # Rate limit por IP
    check_rate_limit(req.client.host if req and req.client else "unknown")

    """
    Procesa texto directo (sin PDF).
    Útil para testing o cuando ya tienes el texto extraído.
    """
    
    if len(text) < 50:
        raise HTTPException(status_code=400, detail="Texto demasiado corto")
    
    try:
        extracted_data, tokens_used = process_with_ai(text, document_type)
        
        return {
            "document_type": document_type,
            "extracted_data": extracted_data,
            "tokens_used": tokens_used,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/templates", dependencies=[Depends(verify_token)])
def get_templates(req: Request = None):
    """Muestra las plantillas de extracción disponibles"""
    # Rate limit por IP
    if req and req.client:
        check_rate_limit(req.client.host)
    return {
        "available_types": list(EXTRACTION_PROMPTS.keys()),
        "templates": {
            k: v[:200] + "..." for k, v in EXTRACTION_PROMPTS.items()
        }
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)