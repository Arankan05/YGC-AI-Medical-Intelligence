# YGC AI Medical Intelligence

An AI-powered medical record management and local healthcare provider discovery platform that transforms unstructured medical documents into structured, actionable, and secure personal health records.

---

## Overview

Medical documents such as prescription notes, diagnostic laboratory reports, consultation summaries, and hospital discharge notes are traditionally stored as physical paper records or fragmented PDF files. This fragmentation makes it difficult for patients to track clinical trends, recognize medication conflicts, or locate relevant local healthcare providers when medical care is needed.

**YGC AI Medical Intelligence** addresses this challenge by providing an end-to-end intelligent extraction pipeline. Uploaded medical documents are parsed, normalized, validated, and structured into unified patient health records, enabling interactive timeline tracking, AI-driven medical analysis, grounded record Q&A, and real-time healthcare provider discovery.

```text
Medical Document (PDF / Image)
              ↓
     PDF / OCR Extraction
              ↓
        Text Cleaning
              ↓
     Gemini AI Extraction
              ↓
   Structured Medical JSON
              ↓
    Pydantic Validation
              ↓
  MedicalPersistenceService
              ↓
    PostgreSQL / Supabase
              ↓
      Medical Dashboard
```

---

## Key Features

### 📄 Document Management
* **Multi-Format Upload**: Upload medical documents including prescriptions, consultation notes, laboratory reports, discharge summaries, and general medical records.
* **PDF & OCR Processing**: Automated text extraction using PyMuPDF with seamless Tesseract OCR fallback for scanned paper documents and medical images.
* **Document Classification**: Automated detection and categorization of document types (`prescription`, `lab_report`, `discharge_summary`, `consultation_note`, `other`).

### 📊 Structured Medical Records
* **Interactive Medical Timeline**: Unified timeline rendering clinical encounters with strict date safety rules.
* **Clinical Findings**: Categorized diagnostic findings with risk levels (`high`, `medium`, `low`), confidence scores, and recommendations.
* **Medication & Prescription Management**: Track active medications, dosage instructions, frequency, and prescription histories.
* **Laboratory Intelligence**: Extracted laboratory test results with numerical values, units, reference ranges, and flag indicators.
* **Allergy Tracking**: Recorded medication and allergen sensitivities with reaction descriptions and severity markers.

### 🤖 AI Intelligence & Anti-Hallucination
* **Gemini Extraction Engine**: Structured medical extraction powered by Gemini AI with strict JSON schema enforcement.
* **Anti-Hallucination Grounding**: Prompt engineering rules that prohibit inventing missing clinical dates or hypothetical medical facts.
* **Medical Record Q&A**: Multi-document question-answering with inline source document citations grounded strictly in the patient's uploaded records.
* **AI Analysis Summary**: Instant document-level medical summaries, risk assessments, and clinical takeaways.

### 🏥 Healthcare Provider Search
* **Location-Based Search**: Search local doctors, clinics, hospitals, and pharmacies by location name or current browser GPS coordinates.
* **OpenStreetMap Integration**: Powered by Nominatim geocoding with Sri Lankan regional preference (`countrycodes=lk`) and Overpass API query engines.
* **Mirror Failover & Resilience**: Automated fallback across multiple public Overpass API endpoints for high availability.
* **Interactive Map**: Dynamic Leaflet map with custom specialty markers, provider distance ranking, and contact details.

### 🔐 Security & Tenant Isolation
* **Authentication**: Supabase JWT authentication guarding all frontend routes and backend REST API endpoints.
* **Strict Patient Isolation**: Every query and database transaction filters strictly by `patient_id == authenticated_patient.id`.
* **Zero Credential Exposure**: Environment-based configuration excluding all API keys and database credentials from version control.

---

## System Architecture

```mermaid
flowchart TD
    Patient(["Patient (Web Browser)"]) --> NextFS["Next.js 15 Frontend\n(React 19 + TypeScript)"]
    NextFS --> SupaAuth["Supabase Auth / JWT Verification"]
    SupaAuth --> FastBE["FastAPI Backend\n(Python 3.14+)"]

    subgraph ProcessingPipeline ["Processing & Intelligence Pipeline"]
        FastBE --> DocProc["Document Processing Service\n(PyMuPDF + Tesseract OCR)"]
        DocProc --> TextClean["Text Normalization"]
        TextClean --> GeminiAI["Gemini AI Service\n(Structured JSON Extraction)"]
        GeminiAI --> PydanticVal["Pydantic Schema Validation"]
        PydanticVal --> MedPersist["MedicalPersistenceService"]
        FastBE --> AIQA["Medical Q&A Engine\n(Grounded Context Retrieval)"]
        FastBE --> ProviderSearch["Healthcare Provider Search\n(Nominatim + Overpass API)"]
    end

    MedPersist --> PostgresDB[("PostgreSQL Database\n(Supabase / SQLAlchemy)")]
    DocProc --> SupaStore[("Supabase Storage\n(Encrypted PDF/Image Files)")]
    AIQA --> PostgresDB
    ProviderSearch --> OSM["OpenStreetMap Services"]
```

---

## Technology Stack

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend Framework** | Next.js 15.5 | App Router, Server Components, Client State |
| **Frontend Language** | TypeScript 5 | End-to-end type safety |
| **Styling & Components** | Tailwind CSS 4, shadcn/ui | Premium responsive UI components |
| **Interactive Maps** | Leaflet 1.9, React-Leaflet | Healthcare provider map rendering |
| **Backend Framework** | FastAPI 0.141 | High-performance asynchronous REST API |
| **Backend Language** | Python 3.14+ | Modern async backend runtime |
| **Database & ORM** | PostgreSQL (Supabase), SQLAlchemy 2.0 | Relational database & ORM mapping |
| **Database Migrations** | Alembic 1.19 | Reversible schema migrations |
| **Authentication** | Supabase Auth, PyJWT | JWT validation & patient session protection |
| **File Storage** | Supabase Storage | Encrypted medical document storage |
| **AI Extraction & Q&A** | Google Gemini AI (`gemini-3.5-flash-lite`) | Structured medical JSON & grounded Q&A |
| **PDF Processing** | PyMuPDF (fitz) | Digital PDF text & layout extraction |
| **OCR Engine** | Tesseract OCR 5 | Optical character recognition for scanned records |
| **Location & Geocoding** | Nominatim, Overpass API | Location geocoding & OpenStreetMap provider search |
| **Containerization** | Docker (`python:3.14-slim`) | Linux production runtime container |
| **Hosting & Cloud** | Vercel (Frontend), Render (Backend) | Production deployment architecture |

---

## Medical Document Processing Pipeline

The document extraction pipeline operates asynchronously to convert unstructured documents into validated database entities:

1. **Document Upload**: Patient uploads a PDF or image via the frontend. File is stored securely in Supabase Storage.
2. **PDF Parsing**: PyMuPDF extracts digital text and layout metadata.
3. **OCR Fallback**: If digital text yield is low or empty (e.g. scanned paper records), Tesseract OCR parses the document images.
4. **Text Cleaning**: Extracted text undergoes cleaning, whitespace normalization, and encoding repair.
5. **Gemini Extraction**: Cleaned text is submitted to Gemini AI with structured extraction prompts.
6. **Structured Output**: Gemini returns structured JSON containing summary, document type, events, medications, lab results, allergies, and findings.
7. **Pydantic Validation**: `ExtractedMedicalRecord` schema validates data types, date formats, and confidence scores.
8. **Medical Persistence**: `MedicalPersistenceService` performs transactional database writes with entity-level idempotency checks.
9. **Dashboard APIs**: Clean REST API endpoints serve structured records to dashboard views, timeline feeds, and safety cards.

> **Anti-Hallucination Rule**: If a medical document lacks specific clinical entities (e.g., no laboratory results present), Gemini is instructed to return an empty array (`[]`). The system never invents missing medical data.

---

## Structured Medical Data Entities

The application normalizes unstructured document content into eight relational schemas:

* **Documents**: Metadata, file path, upload date, document type, and extraction status.
* **Medical Events**: Clinical encounter records (`consultation`, `lab_test`, `procedure`, `admission`, `discharge`, `prescription`).
* **Findings**: Diagnostic conclusions and clinical observations with risk levels (`high`, `medium`, `low`), confidence scores, and recommendations.
* **Medications**: Normalized drug records with dosage, frequency, and instructions.
* **Prescriptions**: Specific prescription occurrences linking medications to patient documents.
* **Laboratory Results**: Diagnostic test metrics with numerical values, units, reference ranges, and abnormal indicators.
* **Allergies**: Recorded allergen sensitivities, severity ratings, and reaction descriptions.
* **AI Analyses**: Document extraction summaries, confidence scores, and Q&A interaction records.

---

## Idempotency & Data Safety

### AI Analysis Idempotency
To prevent duplicate analysis records on document re-extraction, `MedicalPersistenceService` tracks `(patient_id, document_id)` inside `AIAnalysis.result["document_id"]`. Re-extracting an existing document updates the existing `document_extraction` record in-place. QA analysis records (`analysis_type = "qa"`) remain separate and unmerged.

### Finding Idempotency
Finding records enforce document-scoped idempotency bounded by:
$$\text{Finding Identity} = (\text{patient\_id}, \text{source\_document\_id}, \text{title})$$
* Re-extracting Document A updates Document A's findings in-place without creating duplicate database rows.
* Identical finding titles appearing in separate documents (e.g. `High Body Temperature` on Aug 16 vs Aug 20) remain preserved as distinct clinical observations over time.
* A safe, standalone maintenance utility [`clean_duplicate_findings.py`](file:///c:/Users/LENOVO/Downloads/YGC-AI-Medical-Intelligence/backend/app/scripts/clean_duplicate_findings.py) is available with `--dry-run` and `--execute` modes to audit and resolve legacy unlinked `NULL`-source records created prior to the schema migration.

### Clinical Date Safety Rule
The system **never** invents clinical encounter dates or substitutes file upload timestamps as clinical event dates.
* If an explicit clinical date is present in the document text, `event_date` is parsed and stored.
* If no explicit clinical date is present, `event_date` remains `None` (`null` in API responses). Display formatting gracefully falls back to creation timestamps without corrupting stored medical facts.

---

## AI Medical Record Q&A

The Medical Q&A engine enables patients to ask natural language questions about their health history:

```text
User Question
      ↓
Authenticated Patient Context
      ↓
Retrieve Patient Medical Records & Document Content
      ↓
Grounded Extraction Prompt (Strict anti-hallucination rules)
      ↓
Gemini AI Processing
      ↓
Structured Answer + Inline Document Citations
```

* **Grounded Responses**: AI responses are bounded strictly by the patient's uploaded medical records.
* **Source Citations**: Answers reference source documents so patients can verify information directly against original uploads.

---

## Healthcare Provider Search

The healthcare discovery service assists patients in locating nearby medical care:

1. **Location Resolution**: Users specify a location name or use browser GPS coordinates.
2. **Geocoding**: Nominatim geocodes location text into latitude and longitude coordinates with Sri Lankan regional preference (`countrycodes=lk`).
3. **Overpass Querying**: Overpass API queries OpenStreetMap for medical features (`amenity=doctors`, `amenity=clinic`, `amenity=hospital`, `amenity=pharmacy`, `healthcare=*`).
4. **Mirror Failover**: If the primary Overpass server times out or fails, requests automatically attempt fallback mirror endpoints.
5. **Interactive Display**: Providers are ranked by distance, categorized by specialty/type, and rendered on an interactive Leaflet map.

---

## Security & Tenant Isolation

* **Authentication**: Supabase Auth handles user sign-ups and logins. Frontend requests pass JWT bearer tokens to FastAPI.
* **Row-Level Tenant Isolation**: All database queries enforce `patient_id == current_user_patient_id`. Patients can never view, update, or delete records belonging to another patient.
* **Secrets Protection**: All API keys (`AI_API_KEY`, `SUPABASE_KEY`), database URIs (`DATABASE_URL`), and authentication secrets are loaded via `.env` files and environment variables. Secrets are strictly excluded from version control.

---

## Project Structure

```text
YGC-AI-Medical-Intelligence/
├── frontend/                       # Next.js 15 Web Application
│   ├── src/
│   │   ├── app/                    # App Router pages & layouts
│   │   │   ├── (app)/              # Authenticated app routes
│   │   │   │   ├── dashboard/      # Patient overview dashboard
│   │   │   │   ├── documents/      # Document management & upload
│   │   │   │   ├── findings/       # Clinical findings view
│   │   │   │   ├── lab-intelligence/# Laboratory trends & results
│   │   │   │   ├── medications/    # Active medications & safety
│   │   │   │   ├── providers/      # Healthcare provider search & map
│   │   │   │   ├── qa/             # AI Q&A record assistant
│   │   │   │   └── timeline/       # Interactive medical timeline
│   │   │   ├── (auth)/             # Login & registration views
│   │   │   └── page.tsx            # Landing page
│   │   ├── components/             # UI components & badges
│   │   └── lib/                    # API client, types & utilities
│   ├── package.json
│   └── tsconfig.json
│
├── backend/                        # FastAPI Backend Application
│   ├── app/
│   │   ├── api/                    # REST API endpoints
│   │   │   ├── auth.py             # User authentication & profile
│   │   │   ├── documents.py        # Document upload & extraction
│   │   │   ├── lab_intelligence.py # Lab result endpoints
│   │   │   ├── medication_safety.py# Drug interaction checks
│   │   │   ├── provider_discovery.py# Healthcare provider search
│   │   │   ├── qa.py               # AI Q&A endpoints
│   │   │   └── records.py          # Timeline, findings, medications
│   │   ├── core/                   # Security, config & settings
│   │   ├── db/                     # Database setup & session management
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic validation schemas
│   │   ├── scripts/                # Maintenance & cleanup utilities
│   │   └── services/               # Core business logic services
│   │       ├── ai/                 # Gemini AI provider & prompts
│   │       ├── document_processor.py # PDF & OCR text extraction
│   │       ├── medical_persistence_service.py # Transactional DB persistence
│   │       └── provider_discovery_service.py  # Nominatim & Overpass search
│   ├── alembic/                    # Schema migration scripts
│   │   └── versions/               # Reversible Alembic migrations
│   ├── tests/                      # Automated pytest suite (671 tests)
│   ├── Dockerfile                  # Production container definition
│   ├── pyproject.toml
│   └── requirements.txt
│
├── .env.example                    # Global environment template
├── render.yaml                     # Render blueprint specification
└── README.md                       # Documentation
```

---

## Local Development Setup

### Prerequisites
* **Python**: Python 3.14+ (or Python 3.11+)
* **Node.js**: Node.js 20+ (with npm)
* **PostgreSQL / Supabase**: Running PostgreSQL instance or Supabase project
* **Tesseract OCR**:
  * **Windows**: Installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`
  * **Linux/macOS**: Installed via `apt-get install tesseract-ocr` or `brew install tesseract`

### 1. Environment Configuration
Copy `.env.example` to `.env` in both root and backend directories:
```bash
cp .env.example .env
cp .env.example backend/.env
```
Fill in your credentials (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, `AI_API_KEY`).

### 2. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```
Backend API will run at `http://127.0.0.1:8000`. API documentation is available at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
```bash
cd frontend

# Install Node.js dependencies
npm install

# Start Next.js development server
npm run dev
```
Frontend application will run at `http://localhost:3000`.

---

## Environment Variables

| Variable | Description | Example Placeholder |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection URI | `postgresql://postgres:password@localhost:5432/ygc_medical` |
| `SUPABASE_URL` | Supabase project URL | `https://your-project.supabase.co` |
| `SUPABASE_KEY` | Supabase anon/service API key | `your_supabase_anon_key` |
| `AI_PROVIDER` | AI service provider | `gemini` |
| `AI_MODEL` | Gemini model name | `gemini-3.5-flash-lite` |
| `AI_API_KEY` | Google Gemini API key | `your_gemini_api_key` |
| `TESSERACT_CMD` | Path to Tesseract OCR executable | `C:\Program Files\Tesseract-OCR\tesseract.exe` *(Windows)* or `/usr/bin/tesseract` *(Linux)* |
| `NOMINATIM_URL` | Nominatim geocoding API URL | `https://nominatim.openstreetmap.org` |
| `OVERPASS_URL` | Overpass API server URL | `https://overpass-api.de/api/interpreter` |
| `ENVIRONMENT` | Execution environment | `development` or `production` |

---

## Testing & Verification

The project includes an extensive automated test suite for backend services, APIs, schema validation, and persistence idempotency, alongside frontend typechecking and linting tools.

### Run Backend Tests
```bash
cd backend
python -m pytest backend/tests
```
* **Verified Status**: **671 passed backend tests** covering auth, persistence, idempotency, OCR, AI extraction, and REST endpoints.

### Run Frontend Typecheck & Lint
```bash
cd frontend
npm run typecheck
npm run lint
```
* **Verified Status**: **0 TypeScript errors**, **0 ESLint warnings**.

### Code Style & Formatting Check
```bash
git diff --check
```
* **Verified Status**: **Clean** (0 trailing whitespace or blank-line errors).

---

## Production Deployment

The platform is designed for cloud deployment across Vercel, Render, Supabase, and Gemini AI:

```text
GitHub Repository
       │
       ├──> Vercel (Frontend Next.js App)
       │
       └──> Render (Backend FastAPI Container)
                 │
                 ├──> Supabase (PostgreSQL Database & File Storage)
                 │
                 └──> Gemini AI (Medical Extraction & Grounded Q&A)
```

### Backend Containerization (Render)
The backend uses a production-ready Dockerfile (`python:3.14-slim`) defined in [`backend/Dockerfile`](file:///c:/Users/LENOVO/Downloads/YGC-AI-Medical-Intelligence/backend/Dockerfile) and configured via [`render.yaml`](file:///c:/Users/LENOVO/Downloads/YGC-AI-Medical-Intelligence/render.yaml):
* Pre-installs `tesseract-ocr` and `tesseract-ocr-eng` Debian packages inside the Linux container.
* Sets `TESSERACT_CMD=/usr/bin/tesseract`.
* Configures health monitoring on `/health`.

---

## Limitations

* **Document Quality**: Extraction accuracy depends on the legibility of scanned documents, lighting quality of images, and layout complexity.
* **Handwritten Records**: Highly cursive handwritten doctor notes may require manual user review.
* **Language Support**: Default OCR setup focuses on English records (`tesseract-ocr-eng`). Non-English medical documents require additional Tesseract language packages.
* **Provider Map Coverage**: Healthcare provider discovery depends on public OpenStreetMap data completeness in specific geographical regions.

---

## Future Improvements

* **Multi-Language OCR**: Support for additional regional languages (e.g. Sinhala, Tamil) in Tesseract OCR pipeline.
* **Advanced Clinical Trends**: Graphical trend line visualization for blood pressure, blood glucose, and lab metrics over multi-year spans.
* **Automated Appointment Reminders**: Scheduled notifications for medication refills and follow-up medical consultations.
* **FHIR / HL7 Export**: Export personal health data in standard HL7 FHIR format for interoperability with electronic health record (EHR) systems.

---

## University Project Summary

* **Problem**: Paper-based and unorganized PDF medical records prevent patients from tracking health trends, discovering dangerous drug conflicts, or locating nearby doctors when care is needed.
* **Solution**: A secure, AI-powered personal health record system that extracts structured medical data from documents, provides grounded Q&A, detects safety conflicts, and connects patients with local healthcare providers.
* **Main Users**: Patients managing chronic conditions, prescription histories, and diagnostic reports.
* **Main Workflow**: Upload Document $\rightarrow$ PDF/OCR Parsing $\rightarrow$ Gemini AI Structuring $\rightarrow$ Pydantic Validation $\rightarrow$ Database Persistence $\rightarrow$ Dashboard & Provider Search.
* **Expected Benefits**: Improved health literacy, reduced medication errors, instant record access, and streamlined healthcare discovery.

---

## Medical Disclaimer

> **IMPORTANT**: YGC AI Medical Intelligence is an information management and AI-assisted data extraction platform designed for educational and informational purposes. It is **not** a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of a qualified healthcare provider regarding any medical condition or treatment plan. Never disregard professional medical advice or delay seeking it because of information generated by this software.