<script setup>
const emit = defineEmits(['pick'])

const SUGGESTIONS = [
  'Como funciona o ataque furtivo do ladino?',
  'Quais são as condições de vantagem em uma rolagem?',
  'Explique as regras de conjuração de magias de nível 1.',
  'O que acontece quando um personagem cai a 0 pontos de vida?',
]
</script>

<template>
  <div class="empty">
    <div class="empty__mark">
      <v-icon icon="mdi-eye-outline" size="34" />
    </div>

    <h2 class="empty__title">Consulte o oráculo</h2>
    <p class="empty__lead">
      Pergunte sobre as regras de D&amp;D e a resposta vem fundamentada nas
      Free Rules&nbsp;(2024).
    </p>

    <div class="empty__suggestions">
      <button
        v-for="suggestion in SUGGESTIONS"
        :key="suggestion"
        type="button"
        class="empty__suggestion"
        @click="emit('pick', suggestion)"
      >
        <v-icon icon="mdi-arrow-top-right" size="15" class="mr-2 flex-0-0" />
        <span>{{ suggestion }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.empty {
  max-width: 640px;
  margin: auto;
  padding: 32px 8px;
  text-align: center;
}

.empty__mark {
  width: 72px;
  height: 72px;
  margin: 0 auto 22px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: rgb(var(--v-theme-primary));
  border: 1px solid rgba(var(--v-theme-primary), 0.32);
  background: radial-gradient(
    circle at 50% 40%,
    rgba(var(--v-theme-primary), 0.18),
    transparent 70%
  );
}

.empty__title {
  font-family: var(--divination-font-display);
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: 10px;
}

.empty__lead {
  opacity: 0.68;
  margin: 0 auto 30px;
  max-width: 46ch;
  line-height: 1.6;
}

.empty__suggestions {
  display: grid;
  gap: 10px;
  text-align: left;
}

@media (min-width: 720px) {
  .empty__suggestions {
    grid-template-columns: 1fr 1fr;
  }
}

.empty__suggestion {
  display: flex;
  align-items: flex-start;
  width: 100%;
  padding: 13px 15px;
  border-radius: 12px;
  font: inherit;
  font-size: 0.9rem;
  line-height: 1.45;
  color: inherit;
  text-align: left;
  cursor: pointer;
  background: rgba(var(--v-theme-surface-light), 0.7);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  transition:
    border-color 0.18s ease,
    transform 0.18s ease,
    background 0.18s ease;
}

.empty__suggestion:hover {
  background: rgb(var(--v-theme-surface-bright));
  border-color: rgba(var(--v-theme-primary), 0.5);
  transform: translateY(-1px);
}

.empty__suggestion:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .empty__suggestion:hover {
    transform: none;
  }
}
</style>
