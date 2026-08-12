ARG PYTHON_VERSION=3.10

FROM python:${PYTHON_VERSION} AS base

ARG POETRY_VERSION=1.6.1

# Dependencies go into the image's own interpreter rather than a
# virtualenv. Compose bind-mounts ./backend over /usr/src in dev, and
# Poetry prefers an in-project .venv over the one it created at build
# time — so a stray backend/.venv on the host silently shadows every
# dependency in the image ("No module named 'dotenv'"). Without a venv
# there is nothing to shadow.
ENV POETRY_VIRTUALENVS_CREATE=false \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/usr/src/src \
    # This dependency set is large; the defaults give up too early on a
    # slow or flaky connection and fail the whole build.
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    POETRY_REQUESTS_TIMEOUT=120

WORKDIR /usr/src

RUN pip install poetry==${POETRY_VERSION}

# Only the manifests, so dependency layers survive source edits. The lock
# file is required, not optional: without it Poetry re-resolves on every
# build and two builds of the same commit can install different versions.
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

EXPOSE 8000


# --- dev: hot reload ---
# The dev dependency group (ruff, pytest, deepeval) is deliberately not
# installed here: CI runs Poetry directly on the runner, and deepeval is
# heavy enough to dominate the image. Add `--with dev` if you ever want to
# run the suites inside the container.
FROM base AS dev

COPY . ./

# Source normally arrives via the bind mount; --reload-dir keeps the
# watcher off the mounted .venv and caches.
CMD ["uvicorn", "project.main:project_api", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/usr/src/src"]


# --- prod: runtime dependencies only ---
FROM base AS prod

COPY . ./

CMD ["python", "-m", "project.main"]
