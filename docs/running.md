# Running Divination

[Back to the project overview](../README.md).

Run the commands below from the repository root. The application uses
Vue, FastAPI and retrieval-augmented generation (RAG) to answer D&D
questions using retrieved reference material.

## Start the application

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

## Dependencies

The backend uses Poetry, and `pyproject.toml` is the single source of
truth — `poetry.lock` is committed so that an image build installs the
same versions every time. After changing a dependency, relock and commit
both files:

```
 cd backend && poetry lock --no-update
```

CI runs `poetry check --lock`, so a dependency edit committed without
relocking fails there rather than silently resolving to different
versions at build time.

Without Poetry installed locally, the backend image already has it:

```
 docker compose --profile dev run --rm --no-deps \
   -u "$(id -u):$(id -g)" -e HOME=/tmp -e POETRY_CACHE_DIR=/tmp/poetry-cache \
   --entrypoint poetry api-dev lock --no-update
```

The `-u` matters: without it the lock file is written back through the
bind mount owned by root.

The frontend uses npm, with `package-lock.json` committed and installed
via `npm ci`.

### Troubleshooting

Frontend dependencies are held in a named volume, so it must be dropped
when `package.json` changes:

```
 docker volume rm divination_front_node_modules
```
