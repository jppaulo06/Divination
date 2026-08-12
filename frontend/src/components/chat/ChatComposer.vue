<script setup>
import { computed, ref } from 'vue'

import PersonalityMenu from './PersonalityMenu.vue'

const props = defineProps({
  isSending: { type: Boolean, default: false },
  personality: { type: String, required: true },
  isChangingPersonality: { type: Boolean, default: false },
})

const emit = defineEmits(['send', 'change-personality'])

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
      <!-- No class here on purpose: VMenu's root is a fragment, so an
           inherited class is silently dropped rather than applied. -->
      <PersonalityMenu
        compact
        :personality="personality"
        :is-changing="isChangingPersonality"
        @change="emit('change-personality', $event)"
      />

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
  </div>
</template>

<style scoped>
.composer {
  flex: 0 0 auto;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
  /* Generous bottom gap so the field reads as sitting in the layout
     rather than pinned to the window edge. */
  padding: 12px 20px 32px;
}

.composer__inner {
  display: flex;
  /* Bottom-aligned so the field can grow upward on multi-line input while
     both buttons stay on the baseline. */
  align-items: flex-end;
  gap: 8px;
}

.composer__field {
  flex: 1 1 auto;
}

/*
 * Heights are left to Vuetify's size props rather than hand-set, because
 * an icon button resolves to --v-btn-height + 12px:
 *
 *   send  -> size="large"  = 44 + 12 = 56px, matching the field's
 *            --v-input-control-height of 56px
 *   setting -> default size = 36 + 12 = 48px, deliberately smaller since
 *            sending is the primary action and this is a setting
 *
 * The send button previously carried margin-bottom: 4px, which lifted it
 * off the field's bottom edge; alignment now comes from flex-end alone.
 */

@media (max-width: 600px) {
  .composer {
    /* Less than on desktop — vertical space is scarcer — but still clear
       of the edge, plus any on-screen home indicator. */
    padding: 10px 14px calc(20px + env(safe-area-inset-bottom));
  }

  .composer__inner {
    gap: 4px;
  }
}
</style>
