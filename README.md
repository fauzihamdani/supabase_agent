# Project Data AI Agent

A read-only AI agent that answers natural language questions about project data. Built with FastAPI and LangGraph, using Groq as the LLM provider and Supabase Postgres as the data source.

## Features

- Natural language querying of project data (e.g. "show on hold projects", "projects assigned to Fauzi")
- Read-only database access, no insert/update/delete
- Filters by name, status, member, deadline month, and budget range
- Direct filter endpoint for the frontend (no LLM needed)
- Export query results to XLSX
- Refuses questions unrelated to project data

## Tech Stack

- Framework: FastAPI
- Agent orchestration: LangGraph
- LLM: Groq (gpt-oss-120b)
- Database: Supabase Postgres, accessed via a read-only role
- Deployment: Docker on AWS EC2, behind Nginx with HTTPS (Let's Encrypt)

## Project Structure

agent.py       LangGraph agent: router, chat logic, system prompt
database.py    Read-only database connection setup
tools.py       query_projects tool (parameterized SELECT only)
export.py      Export query results to XLSX
server.py      FastAPI app and endpoints
Dockerfile     Container build for deployment

## Getting Started

### Prerequisites

- Python 3.11+
- A Supabase project with a read-only database role
- A Groq API key

### Installation

pip install -r requirements.txt

### Environment Variables

Create a .env file:

SUPABASE_DB_URL=your_supabase_pooler_connection_string
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
ALLOWED_TABLES=projects
CORS_ORIGINS=https://your-frontend-domain.com

Use the Supabase connection pooler string (port 6543), not the direct connection, for compatibility with Docker.

### Run Locally

uvicorn server:app --reload

API available at http://localhost:8000.

### Run with Docker

docker build -t agent-api .
docker run -d -p 8000:8000 --env-file .env --restart unless-stopped agent-api

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| /health | GET | Health check |
| /chat | POST | Natural language chat with the agent |
| /projects/filter | POST | Direct filter query, no LLM |
| /projects/export | POST | Filter and export results to XLSX |

### Example: /chat

Request:
{
  "message": "show on hold projects",
  "history": []
}

Response:
{
  "reply": "Found 14 projects. Here are the on-hold projects.",
  "tool_results": [ ... ]
}

## Security

- Database access uses a dedicated read-only Postgres role, separate from the main account.
- All queries are parameterized; the LLM never writes or executes raw SQL.
- A router step classifies each message before it reaches the agent, rejecting anything unrelated to project data.

## Deployment Notes

The agent runs in a Docker container on an EC2 instance. Nginx reverse-proxies HTTPS traffic to the container, with a certificate issued via Certbot. The domain is managed through DuckDNS since the instance uses a dynamic public IP.