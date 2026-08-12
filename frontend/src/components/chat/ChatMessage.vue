<script setup>
import { computed, ref } from 'vue'

import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  message: { type: Object, required: true },
  canRetry: { type: Boolean, default: false },
})

const emit = defineEmits(['retry'])

const isUser = computed(() => props.message.role === 'user')
const failed = computed(() => Boolean(props.message.failed))

// User text is never treated as markup — it is bound as text, so a
// question containing HTML shows up literally instead of executing.
const renderedHtml = computed(() =>
  isUser.value || failed.value ? '' : renderMarkdown(props.message.content),
)

const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => (copied.value = false), 1600)
  } catch {
    copied.value = false
  }
}
</script>

<template>
  <div class="message" :class="isUser ? 'message--user' : 'message--agent'">
    <div v-if="!isUser" class="message__sigil" :class="{ 'message__sigil--error': failed }">
      <v-icon :icon="failed ? 'mdi-alert-outline' : 'mdi-eye-outline'" size="18" />
    </div>

    <div class="message__body">
      <div class="message__meta">
        {{ isUser ? 'Você' : 'Divination' }}
      </div>

      <div
        class="message__bubble"
        :class="{
          'message__bubble--user': isUser,
          'message__bubble--error': failed,
        }"
      >
        <p v-if="isUser || failed" class="message__plain">
          {{ message.content }}
        </p>
        <!-- eslint-disable-next-line vue/no-v-html -- sanitised in renderMarkdown -->
        <div v-else class="markdown" v-html="renderedHtml" />
      </div>

      <div v-if="!isUser" class="message__actions">
        <v-btn
          v-if="failed && canRetry"
          size="small"
          variant="text"
          color="primary"
          prepend-icon="mdi-refresh"
          @click="emit('retry')"
        >
          Tentar novamente
        </v-btn>
        <v-btn
          v-else-if="!failed"
          size="small"
          variant="text"
          :prepend-icon="copied ? 'mdi-check' : 'mdi-content-copy'"
          @click="copy"
        >
          {{ copied ? 'Copiado' : 'Copiar' }}
        </v-btn>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  max-width: 780px;
  width: 100%;
}

.message--user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message--agent {
  margin-right: auto;
}

.message__sigil {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  margin-top: 22px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: rgb(var(--v-theme-primary));
  border: 1px solid rgba(var(--v-theme-primary), 0.35);
  background: rgba(var(--v-theme-primary), 0.08);
}

.message__sigil--error {
  color: rgb(var(--v-theme-error));
  border-color: rgba(var(--v-theme-error), 0.4);
  background: rgba(var(--v-theme-error), 0.08);
}

.message__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.message--user .message__body {
  align-items: flex-end;
}

.message__meta {
  font-size: 0.7rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  opacity: 0.55;
  margin-bottom: 6px;
}

.message__bubble {
  padding: 14px 18px;
  border-radius: 14px;
  background: rgb(var(--v-theme-surface-light));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  /* Long unbroken strings (URLs, stat blocks) must not widen the column. */
  overflow-wrap: anywhere;
}

.message__bubble--user {
  background: rgba(var(--v-theme-secondary), 0.16);
  border-color: rgba(var(--v-theme-secondary), 0.32);
  border-bottom-right-radius: 4px;
}

.message--agent .message__bubble {
  border-bottom-left-radius: 4px;
}

.message__bubble--error {
  background: rgba(var(--v-theme-error), 0.1);
  border-color: rgba(var(--v-theme-error), 0.35);
}

.message__plain {
  margin: 0;
  white-space: pre-wrap;
}

.message__actions {
  min-height: 28px;
  margin-top: 2px;
  opacity: 0;
  transition: opacity 0.18s ease;
}

.message:hover .message__actions,
.message__actions:focus-within {
  opacity: 1;
}

@media (max-width: 600px) {
  .message__actions {
    opacity: 1;
  }
}
</style>
