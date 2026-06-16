# AI Help Desk — Complaint Classification & Logging Application
## Project Overview
The **AI Help Desk** is a secure, intelligent ticketing and triaging system designed for air-gapped enterprise environments (e.g., AFNET). It processes user complaints in **English, Hindi, and Hinglish (code-mixed)** to automatically identify the responsible applications, expand linked system dependencies, classify the fault category, assign severity levels, and route tickets to the appropriate teams. 
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
ai-helpdesk-app/
├── backend/            # FastAPI source code, ML services, and tests
├── frontend/           # React SPA components, state, and styles
├── database/           # Schema definitions and database migration scripts
├── docs/               # Architecture documents and reference notes
└── offline_assets/     # Deployment manifests and local wheels (excluded from git)

