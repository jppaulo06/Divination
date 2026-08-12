<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <v-app>
    <div class="atmosphere" aria-hidden="true" />
    <RouterView />
  </v-app>
</template>

<style scoped>
/*
 * The dragon art sits on a fixed layer behind the whole app at low
 * opacity, under a vignette, rather than tiling across <body> at full
 * strength where it competed with the transcript text.
 */
.atmosphere {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image:
    radial-gradient(
      1100px 700px at 82% -8%,
      rgba(var(--v-theme-secondary), 0.2),
      transparent 62%
    ),
    radial-gradient(
      900px 620px at 10% 105%,
      rgba(var(--v-theme-primary), 0.13),
      transparent 60%
    ),
    url('/dragon.jpg');
  background-size: cover, cover, cover;
  background-position: center, center, center 22%;
  background-repeat: no-repeat;
}

/* The photograph itself is dimmed separately from the gradients. */
.atmosphere::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(var(--v-theme-background), 0.9),
    rgba(var(--v-theme-background), 0.97)
  );
}
</style>
