# 📄 AI Document Processor API

API que procesa automáticamente PDFs (facturas, CVs, documentos) y extrae datos estructurados usando IA.

**Desarrollado por Jorge Lago Campos** | [LinkedIn](https://www.linkedin.com/in/jorge-lago-campos/)

## 🎯 Casos de Uso Reales

### Para Gestorías y Contables

- ✅ Procesar facturas automáticamente
- ✅ Extraer datos para contabilidad (proveedor, total, IVA, líneas)
- ✅ Reducir entrada manual de datos en 90%

### Para Departamentos de RRHH

- ✅ Procesar CVs masivamente
- ✅ Extraer experiencia, skills, educación
- ✅ Scoring automático de candidatos

### Para PYMEs

- ✅ Digitalizar documentos escaneados
- ✅ Organizar contratos, albaranes, presupuestos
- ✅ Búsqueda inteligente en documentos

## 🚀 Instalación

```bash
git clone [tu-repo]
cd document-processor
pip install -r requirements.txt

# Configurar .env
echo "ANTHROPIC_API_KEY=tu_key" > .env

# Ejecutar (puerto 8001 para no chocar con chatbot)
python main.py
```

Docs en: `http://localhost:8001/docs`

## 📋 Uso

### Procesar Factura

```bash
curl -X POST "http://localhost:8001/process/pdf" \
  -F "file=@factura.pdf" \
  -F "document_type=invoice"
```

## 🔐 Seguridad (Bearer Token) y Rate Limiting

- Configura `.env` con:

  - `API_TOKEN=tu_token_superseguro`
  - `RATE_LIMIT=30` (peticiones por IP en ventana de 60s)

- Los endpoints públicos son: `GET /`, `GET /health`, `GET /docs`, `GET /redoc`, `GET /openapi.json`.
- Los endpoints protegidos requieren header: `Authorization: Bearer <token>`.

### Ejemplo llamada protegida

```bash
curl -X POST "http://localhost:8001/process/text" \
  -H "Authorization: Bearer tu_token_superseguro" \
  -F "text=Lorem ipsum dolor sit amet..." \
  -F "document_type=generic"
```

### Respuestas de error relevantes

- `401 Unauthorized`: falta header o token inválido.
- `429 Too Many Requests`: superado `RATE_LIMIT` en 60 segundos desde la misma IP.

**Respuesta:**

```json
{
  "document_type": "invoice",
  "extracted_data": {
    "numero_factura": "2024-001",
    "fecha": "2024-10-30",
    "proveedor": {
      "nombre": "Acme Corp",
      "cif": "B12345678"
    },
    "total": 1210.0,
    "iva": 210.0
  },
  "confidence": "high"
}
```

### Procesar CV

```bash
curl -X POST "http://localhost:8001/process/pdf" \
  -F "file=@cv.pdf" \
  -F "document_type=cv"
```

### Testing con texto directo

```bash
curl -X POST "http://localhost:8001/process/text" \
  -F "text=FACTURA Nº 2024-001..." \
  -F "document_type=invoice"
```

## 🎨 Frontend de Ejemplo

```html
<!DOCTYPE html>
<html>
  <head>
    <title>Document Processor Demo</title>
    <style>
      body {
        font-family: Arial;
        max-width: 800px;
        margin: 50px auto;
      }
      .upload-box {
        border: 2px dashed #ccc;
        padding: 40px;
        text-align: center;
      }
      #result {
        margin-top: 20px;
        padding: 20px;
        background: #f5f5f5;
      }
    </style>
  </head>
  <body>
    <h1>📄 Procesador de Documentos IA</h1>

    <div class="upload-box">
      <input type="file" id="fileInput" accept=".pdf" />
      <select id="docType">
        <option value="invoice">Factura</option>
        <option value="cv">CV</option>
        <option value="generic">Genérico</option>
      </select>
      <button onclick="processDocument()">Procesar</button>
    </div>

    <div id="result"></div>

    <script>
      async function processDocument() {
        const file = document.getElementById("fileInput").files[0];
        const docType = document.getElementById("docType").value;

        if (!file) {
          alert("Selecciona un archivo");
          return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("document_type", docType);

        document.getElementById("result").innerHTML = "Procesando...";

        const response = await fetch("http://localhost:8001/process/pdf", {
          method: "POST",
          body: formData,
        });

        const data = await response.json();
        document.getElementById("result").innerHTML =
          "<pre>" + JSON.stringify(data.extracted_data, null, 2) + "</pre>";
      }
    </script>
  </body>
</html>
```

## 💰 Modelo de Negocio

### Precios Recomendados

- **Setup básico**: 400€
- **Customización de plantillas**: +150€
- **Integración con su sistema**: +300€
- **Procesamiento mensual**: 0.10€/documento (o flat 100€/mes hasta 1000 docs)

### Clientes Ideales

- Gestorías (5-50 empleados)
- Departamentos de RRHH
- Empresas de selección de personal
- Despachos de abogados
- Empresas de logística

## 🔧 Personalización

### Añadir nuevo tipo de documento

```python
EXTRACTION_PROMPTS["contrato"] = """
Analiza este contrato y extrae:
- Partes contratantes
- Objeto del contrato
- Duración
- Importe
etc...
"""
```

### Mejorar precisión para facturas españolas

Edita el prompt de `invoice` para especificar:

- Formato de CIF español
- IVA 21%
- Campos obligatorios españoles

## 🚀 Deploy

**Railway/Render:** Mismo proceso que el chatbot, pero en puerto 8001

**Docker:**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y poppler-utils
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

## 📊 Roadmap

- [ ] OCR para PDFs escaneados (Tesseract)
- [ ] Soporte para imágenes (JPG, PNG)
- [ ] Procesamiento batch (múltiples archivos)
- [ ] Webhooks para procesamiento asíncrono
- [ ] Exportar a Excel/JSON/CSV
- [ ] Integración con Google Drive/Dropbox

## 🤝 Integración con Otros Sistemas

### Zapier/Make

Expón esta API y conecta con:

- Google Sheets → Facturas automáticas en hoja de cálculo
- Gmail → CVs que llegan por email se procesan automáticamente
- Slack → Notificaciones cuando se procesa un documento

### API Propia del Cliente

```python
# Después de procesar
async def send_to_client_system(data):
    await client_api.post('/invoices', json=data)
```

## 📞 Contacto

**Jorge Lago Campos**

- 📧 lagojorge24@gmail.com
- 💼 [LinkedIn](https://www.linkedin.com/in/jorge-lago-campos/)

---

⭐ **Demo en vivo:** [Añade aquí tu URL de Railway cuando despliegues]
