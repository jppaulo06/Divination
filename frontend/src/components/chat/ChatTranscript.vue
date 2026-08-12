<script setup>
import { nextTick, ref, watch } from 'vue'

import ChatEmptyState from './ChatEmptyState.vue'
import ChatMessage from './ChatMessage.vue'
import TypingIndicator from './TypingIndicator.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  isSending: { type: Boolean, default: false },
})

const emit = defineEmits(['pick', 'retry'])

const scroller = ref(null)
// Only follow the conversation when the reader is already at the bottom;
// yanking the viewport while they scroll back through an answer is worse
// than missing the newest line.
let pinned = true

function onScroll() {
  const el = scroller.value
  if (!el) return
  pinned = el.scrollHeight - el.scrollTop - el.clientHeight < 120
}

async function scrollToBottom() {
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  () => [props.messages.length, props.isSending],
  () => {
    if (pinned) scrollToBottom()
  },
)

// A different conversation always starts at its latest turn.
watch(
  () => props.messages,
  () => {
    pinned = true
    scrollToBottom()
  },
)
</script>

<template>
  <div ref="scroller" class="transcript" @scroll.passive="onScroll">
    <div class="transcript__inner">
      <ChatEmptyState
        v-if="!messages.length && !isSending"
        @pick="emit('pick', $event)"
      />

      <template v-else>
        <ChatMessage
          v-for="(message, index) in messages"
          :key="message.id"
          :message="message"
          :can-retry="index === messages.length - 1 && !isSending"
          @retry="emit('retry')"
        />
        <TypingIndicator v-if="isSending" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.transcript {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.transcript__inner {
  display: flex;
  flex-direction: column;
  gap: 22px;
  min-height: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 28px 20px 8px;
}

@media (max-width: 600px) {
  .transcript__inner {
    padding: 18px 14px 4px;
    gap: 18px;
  }
}
</style>
