<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'

import { useAppTheme } from '@/composables/useAppTheme'
import { useChats } from '@/composables/useChats'
import { usePersonality } from '@/composables/usePersonality'

import ChatComposer from './ChatComposer.vue'
import ChatSidebar from './ChatSidebar.vue'
import ChatTranscript from './ChatTranscript.vue'
import PersonalityMenu from './PersonalityMenu.vue'

const {
  chats,
  currentChatId,
  messages,
  isLoadingChats,
  isSending,
  error,
  chatTitle,
  loadChats,
  startDraft,
  selectChat,
  sendMessage,
  retryLast,
} = useChats()

const { isDark, toggleTheme } = useAppTheme()
const { personality, isChanging, notice, noticeType, setPersonality } =
  usePersonality()

const { mdAndDown, smAndDown } = useDisplay()

// Off-canvas below md, pinned open above it.
const drawer = ref(!mdAndDown.value)
watch(mdAndDown, (isCompact) => (drawer.value = !isCompact))

const composer = ref(null)

// A single awaited init, rather than the previous split across
// beforeMount/mounted where the chat list resolved after a chat had
// already been created and overwrote it.
onMounted(loadChats)

function onNewChat() {
  startDraft()
  if (mdAndDown.value) drawer.value = false
}

function onSelect(id) {
  selectChat(id)
  if (mdAndDown.value) drawer.value = false
}

function onPick(suggestion) {
  composer.value?.fill(suggestion)
}

const showError = computed({
  get: () => Boolean(error.value),
  set: (value) => {
    if (!value) error.value = ''
  },
})

const showNotice = computed({
  get: () => Boolean(notice.value),
  set: (value) => {
    if (!value) notice.value = ''
  },
})
</script>

<template>
  <v-app-bar :height="64" flat class="topbar">
    <v-app-bar-nav-icon
      v-if="mdAndDown"
      aria-label="Alternar lista de conversas"
      @click="drawer = !drawer"
    />

    <div class="topbar__brand">
      <v-icon icon="mdi-eye-outline" color="primary" size="22" />
      <span class="topbar__name">Divination</span>
      <span v-if="!smAndDown" class="topbar__tag">Regras de D&amp;D</span>
    </div>

    <v-spacer />

    <PersonalityMenu
      :personality="personality"
      :is-changing="isChanging"
      :compact="smAndDown"
      class="mr-2"
      @change="setPersonality"
    />

    <v-tooltip :text="isDark ? 'Tema claro' : 'Tema escuro'">
      <template #activator="{ props: tooltipProps }">
        <v-btn
          v-bind="tooltipProps"
          :icon="isDark ? 'mdi-white-balance-sunny' : 'mdi-weather-night'"
          variant="text"
          :aria-label="isDark ? 'Ativar tema claro' : 'Ativar tema escuro'"
          @click="toggleTheme"
        />
      </template>
    </v-tooltip>
  </v-app-bar>

  <v-navigation-drawer
    v-model="drawer"
    :temporary="mdAndDown"
    :permanent="!mdAndDown"
    width="288"
    class="drawer"
  >
    <ChatSidebar
      :chats="chats"
      :current-chat-id="currentChatId"
      :is-loading="isLoadingChats"
      :title-for="chatTitle"
      @new-chat="onNewChat"
      @select="onSelect"
    />
  </v-navigation-drawer>

  <v-main class="main">
    <div class="main__inner">
      <ChatTranscript
        :messages="messages"
        :is-sending="isSending"
        @pick="onPick"
        @retry="retryLast"
      />
      <ChatComposer
        ref="composer"
        :is-sending="isSending"
        @send="sendMessage"
      />
    </div>
  </v-main>

  <v-snackbar v-model="showError" color="error" location="top" :timeout="6000">
    {{ error }}
  </v-snackbar>

  <v-snackbar
    v-model="showNotice"
    :color="noticeType"
    location="top"
    :timeout="3500"
  >
    {{ notice }}
  </v-snackbar>
</template>

<style scoped>
.topbar {
  background: rgba(var(--v-theme-surface), 0.82) !important;
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.topbar__brand {
  display: flex;
  align-items: baseline;
  gap: 9px;
  padding-inline: 6px;
}

.topbar__name {
  font-family: var(--divination-font-display);
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.topbar__tag {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.45;
}

.drawer {
  background: rgba(var(--v-theme-surface), 0.7) !important;
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)) !important;
  backdrop-filter: blur(10px);
}

/* Fixed height so the transcript scrolls internally and the composer
   stays put, instead of the whole page scrolling. */
.main {
  height: 100dvh;
}

.main__inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
</style>
