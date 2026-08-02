<script setup>
import { computed, onMounted } from 'vue'

import { useAgentPodState } from '../composables/useAgentPodState.js'
import { getStatusView } from './statusView.js'

const { health, status, refreshHealth, refreshStatus } = useAgentPodState()
const view = computed(() => getStatusView(health, status))

onMounted(() => {
  void Promise.all([refreshHealth(), refreshStatus()])
})
</script>

<template>
  <section class="box" aria-labelledby="status-heading">
    <h2 id="status-heading" class="title is-4">Runtime status</h2>

    <div
      v-if="view.kind === 'loading'"
      class="notification is-light"
      role="status"
      aria-live="polite"
      data-state="loading"
    >
      Loading AgentPod status…
    </div>

    <div
      v-else-if="view.kind === 'failure'"
      class="notification is-danger is-light"
      role="alert"
      data-state="failure"
    >
      AgentPod status is currently unavailable.
    </div>

    <div v-else class="columns" aria-live="polite">
      <div class="column">
        <article class="notification is-success is-light" :data-state="view.healthState">
          <p class="heading">Health</p>
          <p class="title is-5">{{ view.healthLabel }}</p>
        </article>
      </div>
      <div class="column">
        <article class="notification is-light" :data-state="view.readinessState">
          <p class="heading">Readiness</p>
          <p class="title is-5">{{ view.readinessLabel }}</p>
        </article>
      </div>
    </div>
  </section>
</template>
