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

## Architecture
```text

+------------------------------------------------------------------------+
|                    AIR-GAPPED NETWORK BOUNDARY                         |
|                                                                        |
|  +------------------------------------------------------------------+  |
|  |               CLIENT TIER - Operator Console                     |  |
|  |                                                                  |  |
|  |                 +------------------------------+                 |  |
|  |                 |          React SPA           |                 |  |
|  |                 |      (Vite - Node.js 20)     |                 |  |
|  |                 +------------------------------+                 |  |
|  +------------------------------|-----------------------------------+  |
|                                 | HTTPS REST API                      |
|                                 v                                     |
|  +------------------------------------------------------------------+  |
|  |            APPLICATION TIER - API & Inference                    |  |
|  |                                                                  |  |
|  |                 +------------------------------+                 |  |
|  |                 |        FastAPI Server        |                 |  |
|  |                 |        (Python 3.11)         |                 |  |
|  |                 +--------------|---------------+                 |  |
|  |                                | Local Python Calls / HTTP       |  |
|  |                                v                                 |  |
|  |        +------------------------------------------------+        |  |
|  |        |          Local AI Inference Engine             |        |  |
|  |        |                                                |        |  |
|  |        |  +----------------+    +-------------------+   |        |  |
|  |        |  | Sentence       |    | Ollama / Local    |   |        |  |
|  |        |  | Transformer    |    | LLM Runner        |   |        |  |
|  |        |  | multilingual   |    | Qwen 2.5 - 7B     |   |        |  |
|  |        |  | e5-large       |    |                   |   |        |  |
|  |        |  | (Embeddings)   |    |                   |   |        |  |
|  |        |  +----------------+    +-------------------+   |        |  |
|  |        +-----------------------------|------------------+        |  |
|  +------------------------------|-----------------------------------+  |
|                                 | SQL + Vector Operators             |
|                                 v                                     |
|  +------------------------------------------------------------------+  |
|  |              DATA TIER - Persistence & Search                    |  |
|  |                                                                  |  |
|  |              +--------------------------------+                  |  |
|  |              |   PostgreSQL 16 + pgvector     |                  |  |
|  |              |   Relational Tables +          |                  |  |
|  |              |   vector(1024) HNSW Index      |                  |  |
|  |              +--------------------------------+                  |  |
|  +------------------------------------------------------------------+  |
+------------------------------------------------------------------------+
```
## Technology Stack

- **Backend**: FastAPI (Python 3.11.x)
- **Frontend**: React (Vite, Node.js 20.x LTS)
- **Database**: PostgreSQL 16 + pgvector v0.7
- **Embedding Model**: intfloat/multilingual-e5-base (768-dim, Local)
- **STT Model**: faster-whisper (CPU, int8, Whisper Transformer)
- **TTS Engine**: Windows SAPI5 via pyttsx3 (offline)
- **Auth**: Keycloak 24.0.4 (OAuth2/OIDC, JWT RS256)
- **Containerization**: Docker + Docker Compose

## Repository Layout
```text
backend/
│
├── requirements.txt           # Python dependencies
├── main.py                    # App entry point & server config
├── config.py                  # Environment variables (DB connection strings)
├── database.py                # SQLModel engine & session management
├── models.py                  # SQLModel table schemas
├── schemas.py                 # Pydantic validation for API inputs/outputs
├── voice_schemas.py           # Pydantic schemas for Voice Layer API
├── security.py                # JWT token verification via Keycloak SSO
├── seed_db.py                 # Database seeding with AI vectors
├── generate_static_prompts.py # Pre-recorded TTS audio generation (SAPI5)
│
├── local_models/              # Offline Model Weights (Air-gapped)
│   ├── multilingual-e5-base/  # 768-dim multilingual embedding model
│   └── whisper-small-ct2/     # faster-whisper STT model (460 MB, int8)
│
├── voice/                     # 🎤 PHASE 2 - Voice Layer (
│   ├── __init__.py
│   ├── stt.py                 # Speech-to-Text via faster-whisper
│   │                          # (CPU, int8 quantized, auto language detect)
│   ├── tts.py                 # Text-to-Speech via Windows SAPI5 (pyttsx3)
│   │                          # (Piper VITS implemented but not deployed)
│   ├── validators.py          # Service number validation
│   │                          # (NATO phonetic alphabet + Regex ^\d{7}[A-Z]$)
│   ├── session.py             # Voice session state machine (6 states)
│   ├── audio.py               # Audio format conversion via ffmpeg
│   ├── prompts.py             # Pre-recorded static prompt management
│   └── static_prompts/        # Pre-generated WAV audio files (SAPI5)
│       ├── greeting.wav
│       ├── ask_service_number.wav
│       ├── ask_complaint.wav
│       ├── confirm_yes_no.wav
│       ├── retry_service_number.wav
│       ├── fallback_operator.wav
│       └── goodbye.wav
│
├── services/                  # 🧠 DOMAIN (AI & Business Rules)
│   ├── __init__.py
│   ├── embedder.py            # R-8, R-25 - Multilingual pgvector embeddings
│   ├── classifier.py          # R-11, R-12 - Fault type & severity (keyword-based)
│   ├── search.py              # R-9, R-24 - Candidate ranking & Learning Loop
│   └── dependencies.py        # R-10 - Conditional dependency mapping
│
└── routers/                   # ⚙️  DOMAIN (API Endpoints)
    ├── __init__.py
    ├── admin.py               # R-3, R-4 - App Registry CRUD
    ├── tickets.py             # R-5 to R-21 - Intake & Ticket Lifecycle
    └── voice.py               # R-30 to R-39 - Voice Layer Endpoints
```

### Database Schema

#### 1. Applications
Stores all registered applications supported by the help desk.
```
| Column        | Type         |
| :---          | :---         |
| `id`          | Integer (PK) |
| `name`        | VARCHAR(100) |
| `description` | TEXT         |
| `owning_team` | VARCHAR(100) |
| `contact`     | VARCHAR(200) |
```
**Purpose**: Acts as the master table for all software applications.

#### 2. Application Purposes
Stores business purposes and descriptions of applications.
```
| Column           | Type        |
| :---             | :---        |
| `id`             | Integer (PK)|
| `application_id` | FK          |
| `purpose_text`   | TEXT        |
| `embedding`      | VECTOR(768) |
```
**Purpose**: Allows AI to understand what an application is used for using semantic search.

#### 3. Application Symptoms
Stores common issues and symptoms associated with applications.
```
| Column           | Type        |
| :---             | :---        |
| `id`             | Integer (PK)|
| `application_id` | FK          |
| `symptom_text`   | TEXT        |
| `embedding`      | VECTOR(768) |
```
**Purpose**: Used for automatic application identification from user complaints.
```
#### 4. Application Dependencies
Defines relationships between applications.
```
| Column             | Type         |
| :---               | :---         |
| `id`               | Integer (PK) |
| `source_app_id`    | FK           |
| `dependent_app_id` | FK           |
| `dependency_nature`| VARCHAR(20)  |

**Example**: Email Service → Authentication Service  
**Purpose**: Helps identify root causes when multiple applications are affected.

#### 5. Complaint Intake
Stores raw complaints received from users.
```
| Column                   | Type         |
| :---                     | :---         |
| `id`                     | Integer (PK) |
| `raw_text`               | TEXT         |
| `operator_id`            | VARCHAR(50)  |
| `created_at`             | TIMESTAMP    |
| `complainant_service_no` | VARCHAR(20)  |
| `complainant_name`       | VARCHAR(100) |
| `complainant_unit`       | VARCHAR(100) |
| `complainant_rank`       | VARCHAR(50)  |
```
**Purpose**: Captures original complaint details before ticket creation.

#### 6. Tickets
Main ticket tracking table.
```
| Column                   | Type             |
| :---                     | :---             |
| `ticket_number`          | VARCHAR(20) (PK) |
| `intake_id`              | FK               |
| `complainant_id`         | VARCHAR(50)      |
| `primary_application_id` | FK               |
| `status`                 | VARCHAR(20)      |
| `fault_type`             | VARCHAR(50)      |
| `severity`               | VARCHAR(20)      |
| `complainant_service_no` | VARCHAR(20)      |
| `complainant_rank`       | VARCHAR(50)      |
| `complainant_unit`       | VARCHAR(100)     |
```
**Status Examples**: Open, Assigned, In Progress, Resolved, Closed  
**Severity Examples**: Low, Medium, High, Critical

#### 7. Ticket Related Applications
Stores additional applications involved in a ticket.
```
| Column                   | Type |
| :---                     | :--- |
| `ticket_number`          | FK   |
| `related_application_id` | FK   |
```
**Purpose**: Supports multi-application incidents.

#### 8. Ticket History
Maintains an audit trail of ticket updates.
```
| Column          | Type         |
| :---            | :---         |
| `id`            | Integer (PK) |
| `ticket_number` | FK           |
| `changed_by`    | VARCHAR(50)  |
| `old_status`    | VARCHAR(20)  |
| `new_status`    | VARCHAR(20)  |
| `notes`         | TEXT         |
| `changed_at`    | TIMESTAMP    |
```
**Purpose**: Provides complete ticket lifecycle tracking.

#### 9. Learning Examples
Stores AI learning data.
```
| Column             | Type        |
| :---               | :---        |
| `id`               | Integer (PK)|
| `ticket_number`    | FK          |
| `raw_text`         | TEXT        |
| `text_embedding`   | VECTOR(768) |
| `predicted_app_id` | FK          |
| `confirmed_app_id` | FK          |
```
**Purpose**: Used to improve application prediction accuracy.

