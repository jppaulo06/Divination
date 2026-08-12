# Divination - MAC0499 Capstone Project

This reposity contains the project for "MAC0499 - Trabalho de Formatura Supervisionado"

## Description

The Divination project provides an application that uses the fantasy tabletop role-playing game Dungeons and Dragons (D&D) sourcebooks to help DMs manage players’ adventures.

The system is divided into a front-end and a back-end. The front-end uses the Vue3js framework to provide a user chat interface, and the back-end uses Python+FASTAPI powered by ChatGPT-4o LLM

To answer the questions as faithfully as possible, avoiding LLM Hallucinations, the back-end uses Retrieval-Augmented Generation (RAG) as a structure; this structure reads external data from the D&D Free Rules (2024) page and stores it on a Vector Store Database. When a query is received in the back-end, the RAG retrieves the most relevant chunks from the vector store and sends them to the rest of the system to use as context to give the most accurate answer to the user

## Monograph

The monograph for this capstone project is available on: https://luizcarlosdk.github.io/capstone-project/MonographLuizCarlos.pdf

## How to Run

Copy `backend/.env.sample` to `backend/.env` and fill in the API keys first.

There are two profiles. Every service belongs to one, so plain
`docker compose up` starts nothing — pick one.

### Development (hot reload)

Source is bind-mounted; vite and uvicorn both reload on save.

```
 docker compose --profile dev up --build
```

- frontend: http://localhost:3000
- API: http://localhost:8000 (docs at `/docs`)

### Production (static build)

The frontend is compiled and served as static files by nginx; no source
is mounted.

```
 docker compose --profile prod up --build
```

- frontend: http://localhost:8080
- API: http://localhost:8000

`VITE_BACKEND_URL` is inlined into the bundle at build time, so deploying
anywhere other than localhost means updating both the `front` build arg
and the API's `ALLOWED_ORIGINS` in `docker-compose.yml`.

### Troubleshooting

Frontend dependencies are held in a named volume, so it must be dropped
when `package.json` changes:

```
 docker volume rm divination_front_node_modules
```
