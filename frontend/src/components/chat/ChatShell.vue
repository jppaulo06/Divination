<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'

import { useChats } from '@/composables/useChats'
import { usePersonality } from '@/composables/usePersonality'

import ChatComposer from './ChatComposer.vue'
import ChatSidebar from './ChatSidebar.vue'
import ChatTranscript from './ChatTranscript.vue'

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
  rateMessage,
  retryLast,
} = useChats()

const {
  personality,
  isChanging,
  error: personalityError,
  setPersonality,
} = usePersonality()

const { mdAndDown } = useDisplay()

// Overlay below md, in-layout above it — but hideable either way, so the
// transcript can have the full width. Only the wide layout keeps a
// lasting preference; on a narrow screen the drawer is transient.
const SIDEBAR_KEY = 'divination:sidebar'
const storedSidebar = localStorage.getItem(SIDEBAR_KEY)
const sidebarPreferred = ref(storedSidebar !== 'closed')

const drawer = ref(mdAndDown.value ? false : sidebarPreferred.value)

watch(mdAndDown, (isCompact) => {
  drawer.value = isCompact ? false : sidebarPreferred.value
})

function toggleDrawer() {
  drawer.value = !drawer.value
  if (!mdAndDown.value) {
    sidebarPreferred.value = drawer.value
    localStorage.setItem(SIDEBAR_KEY, drawer.value ? 'open' : 'closed')
  }
}

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

const showPersonalityError = computed({
  get: () => Boolean(personalityError.value),
  set: (value) => {
    if (!value) personalityError.value = ''
  },
})
</script>

<template>
  <v-app-bar :height="64" flat class="topbar">
    <!-- aria-label carries the meaning instead of a visible tooltip. -->
    <v-app-bar-nav-icon
      :aria-label="drawer ? 'Ocultar conversas' : 'Mostrar conversas'"
      :aria-expanded="drawer"
      @click="toggleDrawer"
    />

    <div class="topbar__brand">
      <v-icon icon="mdi-eye-outline" color="primary" size="22" />
      <span class="topbar__name">Divination</span>
    </div>
  </v-app-bar>

  <!-- Deliberately not `permanent`: that prop pins the drawer open and
       ignores v-model, which would make it impossible to hide. -->
  <v-navigation-drawer
    v-model="drawer"
    :temporary="mdAndDown"
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
        @rate="rateMessage"
      />
      <ChatComposer
        ref="composer"
        :is-sending="isSending"
        :personality="personality"
        :is-changing-personality="isChanging"
        @send="sendMessage"
        @change-personality="setPersonality"
      />
    </div>
  </v-main>

  <v-snackbar v-model="showError" color="error" location="top" :timeout="6000">
    {{ error }}
  </v-snackbar>

  <v-snackbar
    v-model="showPersonalityError"
    color="error"
    location="top"
    :timeout="6000"
  >
    {{ personalityError }}
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
