# AletheiaOS v0.1

Neuro-symbolic cognitive architecture with FastAPI, SQLite, RDF/OWL, SHACL, Z3 and Swagger (FastAPI OpenAPI).

## Run
```bash
pip install -r requirements.txt
docker compose up -d rdf4j
uvicorn app.main:app --reload
```
Swagger: http://localhost:8000/docs
