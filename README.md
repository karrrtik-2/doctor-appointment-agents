# Doctor Appointment Multi Agent System

A production-style, multi-agent AI application for handling doctor appointment workflows with a FastAPI backend and Streamlit frontend.

## Overview

This project uses a **supervisor + specialist agent architecture** powered by LangGraph:
- **Supervisor Agent** routes user intent.
- **Information Agent** handles doctor availability and FAQ-like informational requests.
- **Booking Agent** handles appointment booking, cancellation, and rescheduling.

The app is designed to simulate a practical healthcare assistant workflow while keeping components modular and extensible.

## Features

- Multi-agent routing with structured decision outputs
- Appointment operations:
  - Check doctor availability
  - Check specialization-wise availability
  - Book appointment
  - Cancel appointment
  - Reschedule appointment
- FastAPI REST API for backend orchestration
- Streamlit UI for interactive usage
- Environment-based configuration
- Centralized logging and improved runtime error handling

## Architecture

```text
User (Streamlit UI)
        |
        v
FastAPI /execute endpoint
        |
        v
LangGraph Supervisor
   |                 |
   v                 v
Information Agent   Booking Agent
   |                 |
   +-------- Tools Layer --------+
                |
                v
         CSV Availability Data
```

## Project Structure

```text
.
├── appointment_agent.py         # Multi-agent graph and routing logic
├── api.py                       # FastAPI app entrypoint
├── web_app.py                   # Streamlit frontend
├── requirements.txt
├── setup.py
├── .env.example
├── data/
│   ├── doctor_availability.csv # Seed availability data
│   └── availability.csv        # Runtime-updated schedule (generated)
├── models/
│   └── models.py               # Pydantic models for tool inputs
├── prompts/
│   └── supervisor_prompt.py    # Supervisor prompt definition
├── tools/
│   └── appointment_tools.py    # Domain tools used by specialist agents
└── utils/
    ├── config.py               # App-level settings and path management
    ├── llms.py                 # LLM client factory
    └── logger.py               # Logging setup
```

## Tech Stack

- Python 3.10+
- FastAPI + Uvicorn
- Streamlit
- LangChain + LangGraph
- OpenAI chat models via `langchain-openai`
- Pandas (CSV-backed scheduling data)

## Quick Start

### 1) Clone and create environment

```bash
git clone <your-repo-url>
cd doctor-appoitment-multiagent-main
python -m venv .venv
```

Activate environment:

- **Windows (PowerShell)**
```powershell
.venv\Scripts\Activate.ps1
```

- **Linux / macOS**
```bash
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment variables

```bash
cp .env.example .env
```

Update `.env` with your key:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
API_HOST=127.0.0.1
API_PORT=8003
```

### 4) Start backend API

```bash
uvicorn api:app --host 127.0.0.1 --port 8003 --reload
```

### 5) Start Streamlit frontend

In a new terminal:

```bash
streamlit run web_app.py
```

## API Reference

### `GET /health`
Health probe endpoint.

**Response**
```json
{"status": "ok"}
```

### `POST /execute`
Runs the multi-agent workflow.

**Request Body**
```json
{
  "id_number": 1234567,
  "messages": "Book an appointment with john doe on 20-02-2026 10:30"
}
```

**Response Body**
```json
{
  "response": "Successfully done",
  "route": "supervisor",
  "reasoning": "..."
}
```

## Notes on Data Behavior

- The app reads from `data/doctor_availability.csv` by default.
- Once booking/cancellation actions occur, updates are written to `data/availability.csv`.
- On subsequent requests, the app automatically uses the updated file when present.

## Development Tips

- Keep prompts in `prompts/supervisor_prompt.py` focused and deterministic.
- Add new capabilities by:
  1. Defining a new tool in `tools/appointment_tools.py`
  2. Adding/adjusting a specialist agent node in `appointment_agent.py`
  3. Updating supervisor routing instructions in `prompts/supervisor_prompt.py`

## Common Issues

- **`OPENAI_API_KEY` missing**: set it in `.env`.
- **Frontend cannot connect**: ensure FastAPI is running on the same host/port as configured.
- **Validation error for date/id**: follow expected formats from tool schemas (`DD-MM-YYYY` and `DD-MM-YYYY HH:MM`).

## Roadmap Ideas

- Add authentication and per-user conversation memory
- Move from CSV to a transactional database
- Add unit/integration tests and CI pipeline
- Add structured observability and tracing
