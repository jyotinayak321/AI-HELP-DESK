# AI Help Desk — Complaint Classification & Logging Application
## Project Overview
The **AI Help Desk** is a secure, intelligent ticketing and triaging system designed for air-gapped enterprise environments. It processes user complaints in **English, Hindi, and Hinglish (code-mixed)** — via text or voice — to automatically identify the responsible applications, expand linked system dependencies, classify the fault category, assign severity levels, and route tickets to the appropriate teams.
Unlike systems relying on cloud APIs, this application uses **entirely local / self-hosted AI models and infrastructure**: embeddings, LLM classification, speech-to-text, voice activity detection, text-to-speech, WebRTC media transport, and SSO authentication all run inside the air-gapped network. It features a human-in-the-loop validation console and a **retrieval-based learning loop** that allows the system to learn from operator corrections in real time without weight retraining.

### Key Capabilities
*   **Semantic Matching**: Matches natural language complaints against system descriptions using `pgvector` semantic similarity searches.
*   **Conditional Dependency Mapping**: Automatically links related systems only when the fault type matches the nature of their dependency (e.g., pulling in authentication systems on login faults).
*   **Multilingual Processing**: Natively understands code-mixed Hinglish and Hindi text.
*   **LLM Guardrail & Classification**: A local/air-gapped LLM (via vLLM) validates, corrects, and classifies complaints — with a mock mode for offline development without GPU access.
*   **Real-time Learning Loop**: Immediately improves prediction accuracy by searching and retrieving corrected complaints historically as few-shot prompts.
*   **Voice Intake Pipeline**: Real-time Voice Activity Detection (Silero VAD) → Speech-to-Text (faster-whisper) → LLM Guardrail → Text-to-Speech confirmation, callable over both a legacy REST/WebSocket path and a WebRTC path (LiveKit).
*   **SSO Authentication**: Keycloak-issued JWTs protect every API route, with role-based access (operator / team lead) enforced server-side.

## Architecture
```text

╔════════════════════════════════════════════════════════════════════════╗
║                    AI HELP DESK — SYSTEM ARCHITECTURE                 ║
║                Fully Offline / Air-Gapped System (Phases 1–4)         ║
╚════════════════════════════════════════════════════════════════════════╝


┌──────────────────────────────────────────────────────────────────────┐
│                        LAYER 1 — PRESENTATION                        │
│                         React + Vite SPA                              │
│                                                                      │
│  • Complaint Submission Interface (text + voice)                     │
│  • Admin Application Registry                                        │
│  • Ticket Dashboard, Team Queue & Tracking                           │
│  • AI Analysis Display                                               │
│  • Keycloak Login (react-oidc-context)                               │
└──────────────────────────────────────────────────────────────────────┘
                    │                              │
                    │ HTTPS / REST + JSON          │ WebRTC (audio)
                    ▼                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        LAYER 2 — API & BUSINESS LOGIC                │
│                    FastAPI + Python 3.11 + Uvicorn                   │
│                                                                      │
│  main.py                                                             │
│      │                                                               │
│      ├── config.py        → Environment & Settings                   │
│      ├── security.py      → Keycloak JWT verification (JWKS)         │
│      ├── routers/         → API Endpoints                            │
│      │      ├── admin.py    → Application Registry APIs              │
│      │      ├── tickets.py  → Ticket Lifecycle APIs                  │
│      │      ├── voice.py    → Voice Layer (REST/WebSocket) APIs      │
│      │      └── livekit.py  → LiveKit token/status/event APIs        │
│      │                                                               │
│      ├── schemas.py / voice_schemas.py → Request/Response Validation │
│      ├── models.py        → Database ORM Models                      │
│      └── database.py      → PostgreSQL Connection & Sessions         │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                │ Calls AI Services
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         LAYER 3 — AI ENGINE                          │
│                     Fully Offline / Air-Gapped Processing            │
│                                                                      │
│  User Complaint (text or transcribed voice)                          │
│          │                                                           │
│          ▼                                                           │
│  services/llm_client.py                                              │
│  Gemma (via vLLM, OpenAI-compatible API) → Guardrail + Fault/Severity│
│  (MOCK_LLM=True returns realistic mock output for offline dev)       │
│          │                                                           │
│          ▼                                                           │
│  services/embedder.py                                                │
│  multilingual-e5-base → Converts text into 768-dimensional vectors   │
│          │                                                           │
│          ▼                                                           │
│  services/search.py                                                  │
│  pgvector + HNSW → Finds similar historical incidents & few-shots    │
│          │                                                           │
│          ▼                                                           │
│  services/dependencies.py                                            │
│  Dependency Graph → Finds affected applications/services             │
│          │                                                           │
│  services/pipeline.py → Orchestrates the above, shared by REST       │
│  and Voice/LiveKit intake paths                                      │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                │ Read / Write
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         LAYER 4 — DATA LAYER                         │
│                PostgreSQL 16 + pgvector + Docker                     │
│                                                                      │
│  Application Knowledge Base                                          │
│  ├── applications                                                    │
│  ├── app_symptoms                                                    │
│  ├── app_purposes                                                    │
│  └── app_dependencies                                                │
│                                                                      │
│  Ticket Management                                                   │
│  ├── intakes                                                         │
│  ├── tickets                                                         │
│  ├── ticket_rel_apps                                                 │
│  └── ticket_history                                                  │
│                                                                      │
│  AI Learning & RAG Memory                                            │
│  ├── learning_examples                                               │
│  ├── vector(768) embeddings                                          │
│  └── HNSW cosine similarity index                                    │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                │ Local Infrastructure
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      LAYER 5 — DEPLOYMENT STACK                      │
│                    Offline Internal Network (docker-compose)         │
│                                                                      │
│  AI Runtime                                                          │
│  └── vLLM Server → Gemma model (OpenAI-compatible API)               │
│                                                                      │
│  Voice Runtime                                                       │
│  ├── Silero VAD (real-time speech detection)                         │
│  ├── faster-whisper (STT, CTranslate2, int8/GPU)                     │
│  └── SAPI5 / Piper (TTS)                                             │
│                                                                      │
│  Media Transport                                                     │
│  └── LiveKit Server (WebRTC, self-hosted, ports 7880/7881/7882)      │
│                                                                      │
│  Identity                                                            │
│  └── Keycloak (SSO, JWT issuance, port 8080)                         │
│                                                                      │
│  Containers                                                          │
│  └── Docker Compose → PostgreSQL + pgvector, Keycloak, LiveKit       │
│                                                                      │
│  Python Environment                                                  │
│  └── Wheelhouse → Offline pip package installation                   │
│                                                                      │
│  Frontend Build                                                      │
│  └── Vite dist/ static files, served by FastAPI when present         │
└──────────────────────────────────────────────────────────────────────┘


                           END-TO-END FLOW (TEXT)

 User → React UI → FastAPI API → AI Pipeline
                                    │
                                    ├── LLM Guardrail (Gemma / vLLM)
                                    ├── Embedding (e5-base)
                                    ├── Similarity Search (pgvector)
                                    ├── Fault/Severity Classification
                                    └── Dependency Analysis
                                    │
                                    ▼
                            PostgreSQL Database
                                    │
                                    ▼
                     Ticket Creation & AI Response
                                    │
                                    ▼
                        Dashboard / Team Queue / Admin Panel


                           END-TO-END FLOW (VOICE)

 Caller ⇄ LiveKit Room (WebRTC) ⇄ livekit_bridge/adapter.py
                                        │
                                        ▼
                            voice/vad.py (Silero VAD)
                                        │
                                        ▼
                          voice/stt.py (faster-whisper)
                                        │
                                        ▼
                     voice/complaint_processor.py → AI Pipeline (as above)
                                        │
                                        ▼
                          voice/tts.py → spoken confirmation
                                        │
                                        ▼
                              Ticket Creation
```

## Technology Stack
*   **Backend**: FastAPI (Python 3.11.x), Uvicorn
*   **Frontend**: React (Vite, Node.js 20.x LTS), `react-oidc-context` for Keycloak login
*   **Database**: PostgreSQL 16.x + `pgvector` extension (Docker: `pgvector/pgvector:pg16`)
*   **Identity / SSO**: Keycloak 24.x (JWT issuance, JWKS verification in `security.py`)
*   **Embedding Model**: `intfloat/multilingual-e5-base` (Local Sentence-Transformers, 768-dim vectors)
*   **Classification / Guardrail Model**: Gemma (`google/gemma-4-31B-it`) served locally via **vLLM** through an OpenAI-compatible API — replaces the earlier keyword-based classifier; a `MOCK_LLM` flag returns realistic mock output for offline development without a GPU server
*   **VAD**: `silero-vad` (real-time speech activity detection, streaming, CPU/CUDA)
*   **STT Model**: `faster-whisper` (CTranslate2 local wrapper, medium model, int8/GPU)
*   **TTS**: Windows SAPI5 (`pyttsx3`) with Piper (VITS) as an alternate backend
*   **Voice Media Transport**: LiveKit (self-hosted WebRTC media router) alongside a legacy WebSocket/REST audio path, selectable via `LIVEKIT_ENABLED`
*   **Orchestration**: Docker Compose (PostgreSQL, Keycloak, LiveKit)

## Repository Layout

```text
backend/
│
├── requirements.txt           # Python dependencies
├── main.py                    # App entry point, router mounting, static frontend serving
├── config.py                  # Environment variables (DB, Keycloak, LiveKit, vLLM, Voice)
├── database.py                # SQLModel engine & session management
├── models.py                  # SQLModel table schemas
├── schemas.py                 # Pydantic validation for API inputs/outputs
├── voice_schemas.py           # Pydantic schemas for Voice Layer API
├── security.py                # JWT verification via Keycloak SSO (JWKS)
├── seed_db.py                 # Database seeding with AI vectors
├── ai_services.py             # AI service bootstrap/wiring helpers
├── generate_static_prompts.py # Pre-recorded TTS audio generation (SAPI5)
├── download_models.py / download_silero.py / download_weights.py
│                               # Offline model weight fetch scripts (for wheelhouse prep)
│
├── local_models/               # Offline Model Weights (Air-gapped, git-ignored)
│
├── voice/                      # 🎤 PHASE 2 — Voice Layer
│   ├── __init__.py
│   ├── vad.py                  # Silero VAD — real-time speech start/end detection
│   ├── stt.py                  # Speech-to-Text via faster-whisper (auto language detect)
│   ├── tts.py                  # Text-to-Speech via SAPI5 / Piper
│   ├── complaint_processor.py  # Shared complaint pipeline for REST + LiveKit voice paths
│   ├── validators.py           # Service number validation (NATO alphabet + regex)
│   ├── session.py               # Voice session state machine
│   ├── audio.py                 # Audio format conversion via ffmpeg
│   ├── prompts.py               # Pre-recorded static prompt management
│   └── static_prompts/          # Pre-generated WAV audio files (SAPI5)
│
├── livekit_bridge/              # 🎧 PHASE 4 — WebRTC Media Transport
│   ├── __init__.py
│   ├── adapter.py               # LiveKit ↔ Voice Layer integration boundary
│   ├── client.py                 # LiveKit Room Service admin API wrapper
│   ├── connection_manager.py    # Agent room join/leave/reconnect lifecycle
│   ├── room_manager.py          # Room-to-session registry (transport state only)
│   └── token_manager.py         # Short-lived JWTs for room participants
│
├── services/                    # 🧠 DOMAIN (AI & Business Rules)
│   ├── __init__.py
│   ├── embedder.py              # Multilingual pgvector embeddings
│   ├── classifier.py            # Fault type & severity helpers
│   ├── llm_client.py            # Phase 3 — Gemma/vLLM guardrail + classification
│   ├── search.py                # Candidate ranking & Learning Loop
│   ├── dependencies.py          # Conditional dependency mapping
│   └── pipeline.py              # Shared AI pipeline orchestrator (REST + Voice)
│
└── routers/                     # ⚙️  DOMAIN (API Endpoints)
    ├── __init__.py
    ├── admin.py                 # App Registry CRUD
    ├── tickets.py                # Intake & Ticket Lifecycle
    ├── voice.py                  # Voice Layer Endpoints (legacy REST/WebSocket)
    └── livekit.py                # Phase 4 — LiveKit token/status/event endpoints

frontend/src/
│
├── App.jsx                   ← Main router
├── auth.config.js             ← react-oidc-context / Keycloak client config
├── useCurrentUser.js          ← Hook exposing logged-in service_no/role
├── index.css                  ← Global styles
├── index.html                 ← HTML entry point
├── main.jsx                   ← React app bootstrap
│
├── api/                       ← Backend API clients
│   ├── axios.js                ← Axios instance (base URL, auth header)
│   ├── registry.api.js         ← Applications registry API calls
│   ├── tickets.api.js          ← Tickets API calls
│   └── voice.api.js            ← Voice session API calls
│
├── assets/                    ← Images, icons
│
├── components/
│   ├── layout/                 ← Page layout
│   │   ├── Sidebar.jsx          ← Left navigation
│   │   └── Topbar.jsx           ← Top header
│   ├── voice/                   ← 🎤 Voice intake UI (Phase 2/4)
│   │   ├── VoiceRecorder.jsx     ← Mic capture (legacy REST path)
│   │   ├── VoiceSessionPanel.jsx ← Voice session state machine UI
│   │   ├── TranscriptPanel.jsx   ← STT transcript, confidence, language display
│   │   └── LiveKitAudioTransport.jsx ← WebRTC audio room connection (Phase 4)
│   └── ui/                      ← Reusable small components
│       ├── Badge.jsx             ← Status badges (Open, Closed etc)
│       ├── ErrorMessage.jsx      ← Error display
│       ├── LoadingSpinner.jsx    ← Loading animation
│       └── StatCard.jsx          ← Dashboard cards
│
├── hooks/
│   └── useVadStream.js         ← Client-side VAD/audio streaming hook
│
├── constants/
│   └── enums.js                ← Fault types, severity, status values
│
└── pages/                      ← One page per route
    ├── LoginPage.jsx             ← Keycloak login screen
    ├── Dashboard.jsx              ← Home dashboard
    ├── SubmitComplaint.jsx        ← Complaint form (text + voice)
    ├── ClassifyReview.jsx         ← AI classification review
    ├── TicketList.jsx             ← All tickets list
    ├── TicketDetail.jsx           ← Single ticket detail
    ├── TeamQueue.jsx               ← Team-lead queue view
    └── Registry.jsx                ← Application registry
```

### Root-level files
| File | Purpose |
| :--- | :--- |
| `docker-compose.yml` | Orchestrates PostgreSQL+pgvector, Keycloak, and LiveKit for local/offline deployment |
| `database/schema.sql` | Canonical SQL schema (source of truth for the tables below) |
| `keycloak-realm-export.json` | Pre-configured Keycloak realm (clients, roles) imported on container start |
| `livekit-config.yaml` | Self-hosted LiveKit server configuration |
| `generate_keycloak_json.py` | Regenerates the Keycloak realm export from environment-specific values |
| `replace_ips.py` | Utility to rewrite hard-coded host IPs across config files for a new deployment environment |

### Database Schema

#### 1. Applications
Stores all registered applications supported by the help desk.

| Column        | Type         |
| :---          | :---         |
| `id`          | Integer (PK) |
| `name`        | VARCHAR(100) |
| `description` | TEXT         |
| `owning_team` | VARCHAR(100) |
| `contact`     | VARCHAR(200) |

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

#### 4. Application Dependencies
Defines relationships between applications.
```
| Column             | Type         |
| :---               | :---         |
| `id`               | Integer (PK) |
| `source_app_id`    | FK           |
| `dependent_app_id` | FK           |
| `dependency_nature`| VARCHAR(20)  |
```
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

## Local Development Setup

1. **Database, Keycloak & LiveKit** — start the local stack:
   ```bash
   docker compose up -d
   ```
2. **Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   # copy/adjust a .env from config.py defaults (DATABASE_URL, KEYCLOAK_URL, VLLM_API_URL, etc.)
   python seed_db.py       # seed applications + vector embeddings
   python main.py          # or: uvicorn main:app --reload --port 8001
   ```
   Set `AUTH_ENABLED=False` and `MOCK_LLM=True` in `.env` to run fully offline without Keycloak or a vLLM server (both default to sensible dev values in `config.py`).
3. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. API docs are available at `http://localhost:8001/docs` once the backend is running.
