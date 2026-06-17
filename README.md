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

##Architecture

<img width="431" height="222" alt="image" src="https://github.com/user-attachments/assets/f8fc8d96-ea8a-46b9-83e2-cfb61f8b229c" />


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

### Database Schema

#### 1. Applications
Stores all registered applications supported by the help desk.

| Column | Type |
| :--- | :--- |
| `id` | Integer (PK) |
| `name` | VARCHAR(100) |
| `description` | TEXT |
| `owning_team` | VARCHAR(100) |
| `contact` | VARCHAR(200) |

**Purpose**: Acts as the master table for all software applications.

#### 2. Application Purposes
Stores business purposes and descriptions of applications.

| Column | Type |
| :--- | :--- |
| `id` | Integer (PK) |
| `application_id` | FK |
| `purpose_text` | TEXT |
| `embedding` | VECTOR(768) |

**Purpose**: Allows AI to understand what an application is used for using semantic search.

#### 3. Application Symptoms
Stores common issues and symptoms associated with applications.

| Column | Type |
| :--- | :--- |
| `id` | Integer (PK) |
| `application_id` | FK |
| `symptom_text` | TEXT |
| `embedding` | VECTOR(768) |

**Purpose**: Used for automatic application identification from user complaints.

#### 4. Application Dependencies
Defines relationships between applications.

| Column | Type |
| :--- | :--- |
| `id` | Integer (PK) |
| `source_app_id` | FK |
| `dependent_app_id` | FK |
| `dependency_nature` | VARCHAR(20) |

**Example**: Email Service → Authentication Service  
**Purpose**: Helps identify root causes when multiple applications are affected.

#### 5. Complaint Intake
Stores raw complaints received from users.

| Column | Type |
| :--- | :--- |
| `id` | Integer (PK) |
| `raw_text` | TEXT |
| `operator_id` | VARCHAR(50) |
| `created_at` | TIMESTAMP |
| `complainant_service_no` | VARCHAR(20) |
| `complainant_name` | VARCHAR(100) |
| `complainant_unit` | VARCHAR(100) |
| `complainant_rank` | VARCHAR(50) |

**Purpose**: Captures original complaint details before ticket creation.

#### 6. Tickets
Main ticket tracking table.

| Column | Type |
| :--- | :--- |
| `ticket_number` | VARCHAR(20) (PK) |
| `intake_id` | FK |
| `complainant_id` | VARCHAR(50) |
| `primary_application_id` | FK |
| `status` | VARCHAR(20) |
| `fault_type` | VARCHAR(50) |
| `severity` | VARCHAR(20) |
| `complainant_service_no` | VARCHAR(20) |
| `complainant_rank` | VARCHAR(50) |
| `complainant_unit` | VARCHAR(100) |

**Status Examples**: Open, Assigned, In Progress, Resolved, Closed  
**Severity Examples**: Low, Medium, High, Critical

#### 7. Ticket Related Applications
Stores additional applications involved in a ticket.

| Column | Type |
| :--- | :--- |
| `ticket_number` | FK |
| `related_application_id` | FK |

**Purpose**: Supports multi-application incidents.

#### 8. Ticket History
Maintains an audit trail of ticket updates.

| Column | Type |
| :--- | :--- |
| `id` | Integer (PK) |
| `ticket_number` | FK |
| `changed_by` | VARCHAR(50) |
| `old_status` | VARCHAR(20) |
| `new_status` | VARCHAR(20) |
| `notes` | TEXT |
| `changed_at` | TIMESTAMP |

**Purpose**: Provides complete ticket lifecycle tracking.

#### 9. Learning Examples
Stores AI learning data.

| Column | Type |
| :--- | :--- |
| `id` | Integer (PK) |
| `ticket_number` | FK |
| `raw_text` | TEXT |
| `text_embedding` | VECTOR(768) |
| `predicted_app_id` | FK |
| `confirmed_app_id` | FK |

**Purpose**: Used to improve application prediction accuracy.

