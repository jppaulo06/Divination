# Divination — frontend

Vue 3 + Vuetify 3 chat interface for the Divination D&D rules assistant.
Talks to the FastAPI backend over the `/v1` endpoints.

## Setup

```sh
npm install
```

Point the app at the backend with a `.env` file (see `.env.sample`):

```
VITE_BACKEND_URL=http://localhost:8000
```

If unset, it falls back to `http://localhost:8000`.

## Scripts

```sh
npm run dev         # dev server on :3000
npm run build       # production build into dist/
npm run preview     # serve the production build
npm run test:unit   # vitest
npm run lint        # eslint --fix
npm run format      # prettier
```

## Structure

```
src/
  plugins/vuetify.js     Theme definition (dark + light) and component defaults
  services/api.js        The only place that talks HTTP; error normalisation
  composables/
    useChats.js          Conversation state: load, select, send, retry
    useAppTheme.js       Theme toggle, persisted in localStorage
    usePersonality.js    POST /v1/context, persisted in localStorage
  utils/markdown.js      marked + DOMPurify; renderMarkdown / toPlainText
  components/chat/
    ChatShell.vue        Layout: app bar, drawer, transcript, composer
    ChatSidebar.vue      Conversation list
    ChatTranscript.vue   Scroll container and auto-follow behaviour
    ChatMessage.vue      One turn, user or assistant
    ChatComposer.vue     Textarea + send
    ChatEmptyState.vue   First-run state with suggested prompts
    PersonalityMenu.vue  Restritiva / Criativa selector
    TypingIndicator.vue  Pending-answer affordance
```

### Conventions

- **Colour lives in the theme, not in components.** `plugins/vuetify.js` is the
  single source; components reference `--v-theme-*` custom properties so light
  and dark stay in sync.
- **All HTTP goes through `services/api.js`.** Request bodies use the camelCase
  aliases the backend declares (`to_camel` on its pydantic models).
- **Assistant output is sanitised.** Model output is untrusted by the time it
  reaches the DOM: it is parsed by `marked` then cleaned by DOMPurify before
  being bound with `v-html`. User input is bound as text, never as markup.
- **Roles come from the backend `type` field** (`human`/`ai`), not from the
  index of the message.

## Docker

`docker-compose.yml` mounts an anonymous volume over `/app/node_modules`, so
that volume must be renewed whenever dependencies change, or the container
will run against a stale tree:

```sh
docker compose build front
docker compose up --force-recreate --renew-anon-volumes front
```
