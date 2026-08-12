<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  isSending: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const draft = ref('')
const field = ref(null)

const canSend = computed(() => draft.value.trim().length > 0 && !props.isSending)

function submit() {
  if (!canSend.value) return
  emit('send', draft.value)
  draft.value = ''
}

/** Lets the parent drop a suggested prompt in and focus the field. */
function fill(text) {
  draft.value = text
  field.value?.focus()
}

defineExpose({ fill })
</script>

<template>
  <div class="composer">
    <div class="composer__inner">
      <v-textarea
        ref="field"
        v-model="draft"
        :disabled="isSending"
        auto-grow
        rows="1"
        max-rows="6"
        placeholder="Digite sua pergunta sobre as regras…"
        aria-label="Digite sua pergunta"
        class="composer__field"
        @keydown.enter.exact.prevent="submit"
      />

      <v-btn
        :disabled="!canSend"
        :loading="isSending"
        icon="mdi-send"
        color="primary"
        size="large"
        rounded="lg"
        class="composer__send"
        aria-label="Enviar pergunta"
        @click="submit"
      />
    </div>

    <p class="composer__hint">
      <kbd>Enter</kbd> envia · <kbd>Shift</kbd>+<kbd>Enter</kbd> quebra linha
    </p>
  </div>
</template>

<style scoped>
.composer {
  flex: 0 0 auto;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
  padding: 10px 20px 14px;
}

.composer__inner {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.composer__field {
  flex: 1 1 auto;
}

.composer__send {
  margin-bottom: 4px;
}

.composer__hint {
  margin: 8px 0 0;
  font-size: 0.7rem;
  text-align: center;
  opacity: 0.45;
}

.composer__hint kbd {
  font-family: inherit;
  font-size: 0.68rem;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(var(--v-border-color), 0.12);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

@media (max-width: 600px) {
  .composer {
    padding: 8px 14px 12px;
  }

  .composer__hint {
    display: none;
  }
}
</style>
