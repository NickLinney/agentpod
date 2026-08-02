<script setup>
import StatusDashboard from './components/StatusDashboard.vue'

const projectCode = 'NLSW000004'
</script>

<template>
  <main class="section">
    <div class="container">
      <span class="tag is-info is-light">{{ projectCode }}</span>
      <h1 class="title mt-4">NickLinney.AgentPod</h1>
      <p class="subtitle">AgentPod-RT1 local runtime status</p>
      <StatusDashboard />
    </div>
  </main>
</template>
