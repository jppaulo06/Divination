<script setup>
import { ref, watch } from 'vue'
import { useDisplay } from 'vuetify'

/**
 * Shell for every /admin route: app bar, sectioned sidebar, page frame.
 *
 * Navigation lives here rather than in each view's own app bar, which is
 * what the pages did before — every new page meant wedging another button
 * into a neighbour's header, so the routes formed a chain instead of a
 * structure.
 */
const SECTIONS = [
  {
    items: [
      {
        label: 'Monitoramento',
        icon: 'mdi-radar',
        to: { name: 'admin-monitoring' },
      },
    ],
  },
  {
    label: 'Curadoria',
    items: [
      {
        label: 'Amostragem',
        icon: 'mdi-scale-balance',
        to: { name: 'curation-sampling' },
      },
      {
        label: 'Defeitos',
        icon: 'mdi-bug-outline',
        to: { name: 'curation-defects' },
      },
    ],
  },
]

const { mdAndDown } = useDisplay()
const drawer = ref(!mdAndDown.value)

watch(mdAndDown, isCompact => {
  drawer.value = !isCompact
})
</script>

<template>
  <v-app-bar :height="64" flat class="topbar">
    <v-app-bar-nav-icon
      :aria-label="drawer ? 'Ocultar menu' : 'Mostrar menu'"
      :aria-expanded="drawer"
      @click="drawer = !drawer"
    />

    <div class="topbar__brand">
      <v-icon icon="mdi-eye-outline" color="primary" size="22" />
      <span class="topbar__name">Divination</span>
      <span class="topbar__scope">admin</span>
    </div>

    <v-spacer />

    <v-btn
      variant="text"
      prepend-icon="mdi-message-text-outline"
      :to="{ name: 'home' }"
    >
      Abrir o chat
    </v-btn>
  </v-app-bar>

  <v-navigation-drawer
    v-model="drawer"
    :temporary="mdAndDown"
    width="248"
    class="drawer"
  >
    <v-list density="compact" nav>
      <template v-for="(section, index) in SECTIONS" :key="index">
        <v-list-subheader v-if="section.label">
          {{ section.label }}
        </v-list-subheader>

        <v-list-item
          v-for="item in section.items"
          :key="item.label"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.label"
          rounded="lg"
        />
      </template>
    </v-list>
  </v-navigation-drawer>

  <v-main class="main">
    <div class="frame">
      <RouterView />
    </div>
  </v-main>
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

.topbar__scope {
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.55;
}

.drawer {
  background: rgba(var(--v-theme-surface), 0.7) !important;
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)) !important;
  backdrop-filter: blur(10px);
}

.main {
  min-height: 100dvh;
}

.frame {
  max-width: 1040px;
  margin: 0 auto;
  padding: 26px 20px 72px;
}
</style>
