<script setup>
defineProps({
  chats: { type: Array, required: true },
  currentChatId: { type: String, default: null },
  isLoading: { type: Boolean, default: false },
  titleFor: { type: Function, required: true },
})

const emit = defineEmits(['new-chat', 'select'])
</script>

<template>
  <div class="sidebar">
    <div class="sidebar__head">
      <v-btn
        block
        color="primary"
        prepend-icon="mdi-plus"
        size="large"
        @click="emit('new-chat')"
      >
        Novo chat
      </v-btn>
    </div>

    <div class="sidebar__label">Conversas</div>

    <div class="sidebar__scroll">
      <div v-if="isLoading" class="sidebar__state">
        <v-progress-circular indeterminate size="20" width="2" color="primary" />
        <span>Carregando…</span>
      </div>

      <p v-else-if="!chats.length" class="sidebar__empty">
        Nenhuma conversa ainda. Faça a primeira pergunta para começar.
      </p>

      <v-list v-else class="sidebar__list" bg-color="transparent" nav>
        <v-list-item
          v-for="chat in chats"
          :key="chat.id"
          :active="chat.id === currentChatId"
          class="sidebar__item"
          rounded="lg"
          @click="emit('select', chat.id)"
        >
          <template #prepend>
            <v-icon icon="mdi-message-text-outline" size="17" />
          </template>
          <v-list-item-title class="sidebar__item-title">
            {{ titleFor(chat) }}
          </v-list-item-title>
        </v-list-item>
      </v-list>
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px 12px 12px;
}

.sidebar__head {
  flex: 0 0 auto;
  margin-bottom: 20px;
}

.sidebar__label {
  flex: 0 0 auto;
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.5;
  padding: 0 8px 8px;
}

.sidebar__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
}

.sidebar__state {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
  font-size: 0.85rem;
  opacity: 0.7;
}

.sidebar__empty {
  padding: 4px 8px;
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.55;
  opacity: 0.5;
}

.sidebar__item {
  margin-bottom: 4px;
  border: 1px solid transparent;
}

.sidebar__item--active,
.sidebar__item.v-list-item--active {
  border-color: rgba(var(--v-theme-primary), 0.4);
  background: rgba(var(--v-theme-primary), 0.1);
}

.sidebar__item-title {
  font-size: 0.85rem;
  /* Titles are one line; the full question lives in the transcript. */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
