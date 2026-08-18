<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <header class="head">
    <div class="head__text">
      <h1 class="head__title">{{ title }}</h1>
      <p v-if="subtitle" class="head__subtitle">{{ subtitle }}</p>
    </div>
    <!-- Per-page actions; the app bar stays global. -->
    <div class="head__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.head {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.head__text {
  min-width: 0;
  flex: 1 1 auto;
}

.head__title {
  font-family: var(--divination-font-display);
  font-size: 1.35rem;
  font-weight: 600;
  margin: 0;
  letter-spacing: 0.02em;
}

.head__subtitle {
  margin: 4px 0 0;
  font-size: 0.82rem;
  opacity: 0.6;
}

.head__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
