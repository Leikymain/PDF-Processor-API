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
