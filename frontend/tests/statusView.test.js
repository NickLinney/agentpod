import assert from 'node:assert/strict'
import test from 'node:test'

import { getStatusView } from '../src/components/statusView.js'

function resource(data = null) {
  return { loading: false, data, error: null }
}

function statusData({ configured, ready, status }) {
  return {
    status,
    dependencies: {
      ollama: { configured, ready, detail: ready ? 'ready' : 'safe-detail' },
    },
  }
}

test('loading is public until both resources are available', () => {
  assert.deepEqual(
    getStatusView(
      { loading: true, data: null, error: null },
      resource(statusData({ configured: true, ready: true, status: 'ready' })),
    ),
    { kind: 'loading' },
  )
  assert.deepEqual(getStatusView(resource(), resource()), { kind: 'loading' })
})

test('healthy and ready state uses only established response fields', () => {
  assert.deepEqual(
    getStatusView(
      resource({ status: 'healthy' }),
      resource(statusData({ configured: true, ready: true, status: 'ready' })),
    ),
    {
      kind: 'available',
      healthState: 'healthy',
      healthLabel: 'Healthy',
      readinessState: 'ready',
      readinessLabel: 'Ready',
    },
  )
})

test('configured but unavailable dependency is degraded', () => {
  assert.deepEqual(
    getStatusView(
      resource({ status: 'healthy' }),
      resource(statusData({ configured: true, ready: false, status: 'degraded' })),
    ).readinessLabel,
    'Degraded',
  )
})

test('unconfigured dependency is identified without invented detail', () => {
  const view = getStatusView(
    resource({ status: 'healthy' }),
    resource(statusData({ configured: false, ready: false, status: 'degraded' })),
  )
  assert.equal(view.readinessState, 'unconfigured')
  assert.equal(view.readinessLabel, 'Unconfigured')
  assert.deepEqual(Object.keys(view).sort(), [
    'healthLabel',
    'healthState',
    'kind',
    'readinessLabel',
    'readinessState',
  ])
})

test('safe failure view discards resource errors and malformed state', () => {
  const privateError = {
    code: 'network_error',
    message: 'private-host-and-configuration-marker',
  }
  const views = [
    getStatusView(
      { loading: false, data: null, error: privateError },
      resource(statusData({ configured: true, ready: true, status: 'ready' })),
    ),
    getStatusView(resource({ status: 'unknown' }), resource({ status: 'ready' })),
  ]

  for (const view of views) {
    assert.deepEqual(view, { kind: 'failure' })
    assert.doesNotMatch(JSON.stringify(view), /private-host|configuration-marker/)
  }
})
