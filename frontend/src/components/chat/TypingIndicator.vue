<template>
  <div class="typing">
    <div class="typing__sigil">
      <v-icon icon="mdi-eye-outline" size="18" />
    </div>
    <div class="typing__body">
      <div class="typing__meta">Divination</div>
      <!--
        The dots are decorative, so the pending state is carried by
        role="status" and its label. Without those, removing the visible
        text would leave assistive technology with a CSS animation and no
        way to know an answer is on the way.
      -->
      <div
        class="typing__bubble"
        role="status"
        aria-label="Consultando as regras"
      >
        <span class="typing__dots" aria-hidden="true">
          <i /><i /><i />
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.typing {
  display: flex;
  gap: 12px;
  max-width: 780px;
  margin-right: auto;
}

.typing__sigil {
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
  animation: pulse 1.8s ease-in-out infinite;
}

.typing__meta {
  font-size: 0.7rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  opacity: 0.55;
  margin-bottom: 6px;
}

.typing__bubble {
  display: inline-flex;
  align-items: center;
  /* Dots are the only child now, so the bubble is a small pill rather
     than a labelled row. */
  padding: 14px 18px;
  border-radius: 14px 14px 14px 4px;
  background: rgb(var(--v-theme-surface-light));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.typing__dots {
  display: inline-flex;
  gap: 4px;
}

.typing__dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  animation: blink 1.4s ease-in-out infinite;
}

.typing__dots i:nth-child(2) {
  animation-delay: 0.2s;
}

.typing__dots i:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(var(--v-theme-primary), 0.28);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(var(--v-theme-primary), 0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .typing__sigil,
  .typing__dots i {
    animation: none;
  }
}
</style>
