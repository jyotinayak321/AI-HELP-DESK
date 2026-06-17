# AI Help Desk — Complaint Classification & Logging Application
## Project Overview
The **AI Help Desk** is a secure, intelligent ticketing and triaging system designed for air-gapped enterprise environments. It processes user complaints in **English, Hindi, and Hinglish (code-mixed)** to automatically identify the responsible applications, expand linked system dependencies, classify the fault category, assign severity levels, and route tickets to the appropriate teams. 
Unlike systems relying on cloud APIs, this application uses **entirely local AI models** for embeddings, classification, speech-to-text, and text-to-speech. It features a human-in-the-loop validation console and a **retrieval-based learning loop** that allows the system to learn from operator corrections in real time without weight retraining.
### Key Capabilities
*   **Semantic Matching**: Matches natural language complaints against system descriptions using `pgvector` semantic similarity searches.
*   **Conditional Dependency Mapping**: Automatically links related systems only when the fault type matches the nature of their dependency (e.g., pulling in authentication systems on login faults).
*   **Multilingual Processing**: Natively understands code-mixed Hinglish and Hindi text.
*   **Real-time Learning Loop**: Immediately improves prediction accuracy by searching and retrieving corrected complaints historically as few-shot prompts.
*   **Phased Voice Integration**: Features speech-to-text intake and text-to-speech confirmation capabilities (Phase 2/3).


## Technology Stack
*   **Backend**: FastAPI (Python 3.11.x)
*   **Frontend**: React (Vite, Node.js 20.x LTS)
*   **Database**: PostgreSQL 16.x + `pgvector` v0.7.x extension
*   **Embedding Model**: `intfloat/multilingual-e5-large` (Local Sentence-Transformers)
*   **Inference Model**: `Qwen/Qwen2.5-7B-Instruct-GGUF` (Local via Ollama/llama.cpp)
*   **STT Model**: `Systran/faster-whisper-medium` (CTranslate2 Local Wrapper)
*   **TTS Model**: `MyShell-AI/MeloTTS-English-Hindi` (Local Inference)

  
## Repository Layout
```text

backend/
│
├── app/
│ ├── __init__.py
│ ├── main.py # FastAPI application initialization & middle
│ │
│ ├── api/ # API Routing Layer
│ │ ├── __init__.py
│ │ ├── deps.py # Dependency injection (DB session, AI models
│ │ └── v1/
│ │ ├── router.py # Combines all sub-routers
│ │ ├── applications.py # Endpoints for registry & dependency mapping
│ │ ├── intake.py # Endpoint for complaint classification (R-5,
│ │ ├── tickets.py # Endpoints for ticket lifecycle & routing (R
│ │ └── learning.py # Endpoints for confirming examples (R-22)
│ │
│ ├── core/ # Global configuration & security
│ │ ├── config.py # Environment variables, model paths, system 
│ │ └── database.py # SQLAlchemy engine setup and SessionLocal cl
│ │
│ ├── db/ # Data Access Layer
│ │ ├── base.py # Import all models for Alembic migrations
│ │ ├── base_class.py # Declarative base class with standard mixins
│ │ └── seed.py # Initial registry database seed (R-4)
│ │
│ ├── models/ # SQLAlchemy ORM Models
│ │ ├── application.py
│ │ ├── dependency.py
│ │ ├── ticket.py
│ │ ├── learning.py
│ │ └── call_session.py
│ │
│ ├── schemas/ # Pydantic Schemas (Data Validation)
│ │ ├── application.py
│ │ ├── dependency.py
│ │ ├── ticket.py
│ │ ├── intake.py
│ │ └── learning.py
│ │
│ ├── services/ # Business Logic Layer
│ │ ├── ticketing.py # Ticket numbers generation, auto-routing rul
│ │ └── classification.py # Dependency expansion, confidence rank logic
│ │
│ └── ai/ # AI Inference Layer (Air-gapped models execu
│ ├── __init__.py
│ ├── embedder.py # HuggingFace SentenceTransformers integratio
│ └── llm.py # Ollama / Local LLM API runner client
│
├── tests/ # Testing Suite
│ ├── conftest.py # DB test session and mock models setup
│ ├── test_api/ # REST API tests
│ └── test_ai/ # Embedding & classification pipeline unit te
│
├── alembic/ # Database Migrations folder
├── requirements.txt # Python dependencies (pinned versions)
└── Dockerfile # Self-contained backend runner container

