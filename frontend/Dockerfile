# Pinned rather than :lts-alpine so a new Node major cannot change the
# build under an unchanged commit.
FROM node:22-alpine AS deps

WORKDIR /app

# The defaults give up quickly on a slow or flaky link, which fails the
# whole build partway through the dependency download.
ENV NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_TIMEOUT=120000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000

# npm ci installs exactly what package-lock.json pins.
COPY package*.json ./
RUN npm ci


# --- dev: vite dev server with hot reload ---
FROM deps AS dev

COPY . ./

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host"]


# --- build: emits the static bundle ---
FROM deps AS build

# Vite inlines VITE_* at build time, so the backend URL has to be known
# here — it cannot be supplied when the container starts.
ARG VITE_BACKEND_URL=http://localhost:8000
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

COPY . ./
RUN npm run build


# --- prod: static bundle behind nginx ---
FROM nginx:alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
