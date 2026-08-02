const LOADING_VIEW = Object.freeze({ kind: 'loading' })
const FAILURE_VIEW = Object.freeze({ kind: 'failure' })

function availableView(readinessState, readinessLabel) {
  return Object.freeze({
    kind: 'available',
    healthState: 'healthy',
    healthLabel: 'Healthy',
    readinessState,
    readinessLabel,
  })
}

export function getStatusView(health, status) {
  if (health.loading || status.loading) {
    return LOADING_VIEW
  }
  if (health.error || status.error) {
    return FAILURE_VIEW
  }
  if (!health.data || !status.data) {
    return LOADING_VIEW
  }
  if (health.data.status !== 'healthy') {
    return FAILURE_VIEW
  }

  const ollama = status.data.dependencies?.ollama
  if (!ollama) {
    return FAILURE_VIEW
  }
  if (status.data.status === 'ready' && ollama.ready) {
    return availableView('ready', 'Ready')
  }
  if (!ollama.configured) {
    return availableView('unconfigured', 'Unconfigured')
  }
  return availableView('degraded', 'Degraded')
}
