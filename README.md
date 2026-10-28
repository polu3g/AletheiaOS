# AletheiaOS v0.1

AletheiaOS is a neuro-symbolic cognitive architecture that integrates episodic and semantic memory, reasoning, planning, and logging. It leverages modern technologies like FastAPI, SQLite, RDF/OWL, SHACL, Z3, and Swagger (FastAPI OpenAPI) to create a robust and extensible system.

---

## Features

- **Cognitive Engine**: Processes input text, infers knowledge, and generates plans.
- **Memory Modules**:
  - Episodic Memory: Stores events and experiences.
  - Semantic Memory: Stores facts, knowledge, and inferences.
- **Reasoning**:
  - RDF/OWL-based reasoning using `rdflib`.
  - SHACL validation for RDF data integrity.
  - Constraint solving with Z3.
- **Planning**: Goal-oriented planning based on inferences and reasoning.
- **Logging**: Trace logging for cognitive processes and debugging.
- **World Model**: Maintains the state of the system and its environment.

---

## Project Structure

```
app/
├── db.py                # SQLite database setup
├── main.py              # FastAPI application entry point
├── cognitive/
│   └── engine.py        # Cognitive engine implementation
├── logging/
│   └── trace.py         # Trace logger
├── memory/
│   ├── episodic.py      # Episodic memory module
│   └── semantic.py      # Semantic memory module
├── planning/
│   └── planner.py       # Goal planner
├── reasoning/
│   ├── rdf_store.py     # RDF store for reasoning
│   ├── shacl_validator.py # SHACL validation
│   └── z3_engine.py     # Z3 constraint engine
├── world_model/
│   └── state.py         # World model state
docs/
├── architecture.md      # System architecture documentation
images/
├── architecture.png     # Architecture diagram
├── cognitive_loop.png   # Cognitive loop diagram
ontology/
├── aletheia.owl         # Ontology file
├── shapes.ttl           # SHACL shapes for validation
tests/
├── test_engine.py       # Unit tests for the cognitive engine
docker-compose.yml       # Docker setup for RDF4J
requirements.txt         # Python dependencies
```

---

## Installation

Follow these steps to set up and run AletheiaOS:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/AletheiaOS.git
   cd AletheiaOS
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the RDF4J service**:
   ```bash
   docker compose up -d rdf4j
   ```

4. **Run the FastAPI application**:
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Access the Swagger UI**:
   Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to explore the API.

---

## Testing

Run the unit tests to ensure everything is working correctly:
```bash
pytest tests/
```

---

## Documentation

- **Architecture**: Refer to [docs/architecture.md](docs/architecture.md) for a detailed explanation of the system's design.
- **Diagrams**: Check [images/architecture.png](images/architecture.png) and [images/cognitive_loop.png](images/cognitive_loop.png) for visual representations of the architecture and cognitive loop.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.
