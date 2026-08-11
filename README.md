# YGC AI Medical Intelligence

AI-powered medical record intelligence and local healthcare provider recommendation platform.

## Project

This project is being developed for the YGC AI Competition 2026 Final Round.

The system extends the Round 1 AI Medical Report & Prescription Cross-Checker with a Local Doctor Recommendation feature.

## Core Features

- Medical document upload
- PDF text extraction
- OCR for scanned documents
- Structured medical information extraction
- Unified patient timeline
- Medication analysis
- Drug interaction detection
- Duplicate prescription detection
- Dosage conflict detection
- Allergy contradiction detection
- Laboratory trend analysis
- Multi-document medical Q&A
- RAG-based evidence retrieval
- Risk and confidence scoring
- Medical specialty matching
- Location-based healthcare provider search
- Real OpenStreetMap healthcare data
- Provider ranking
- Interactive healthcare map

## Technology Stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

### Database
- Supabase PostgreSQL
- pgvector

### Storage
- Supabase Storage

### AI
- LLM
- Embeddings
- RAG
- Provider-independent AI service
- Optional Ollama

### Document Processing
- PyMuPDF
- Tesseract OCR

### Healthcare Provider Search
- OpenStreetMap
- Nominatim
- Overpass API

### Maps
- Leaflet

### Deployment
- Vercel
- Render

## Repository Structure

```text
frontend/
backend/
docs/