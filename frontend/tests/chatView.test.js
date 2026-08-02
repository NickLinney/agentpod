import assert from 'node:assert/strict'
import test from 'node:test'

import { getChatView } from '../src/components/chatView.js'

function chat(overrides = {}) {
  return { loading: false, response: null, error: null, ...overrides }
}

test('idle and blank-invalid states are fixed', () => {
  assert.deepEqual(getChatView(chat(), false), { kind: 'idle' })
  assert.deepEqual(getChatView(chat(), true), {
    kind: 'invalid',
    message: 'Enter a prompt before submitting.',
  })
})

test('submitting state suppresses stale result and error', () => {
  assert.deepEqual(
    getChatView(
      chat({
        loading: true,
        response: 'stale response',
        error: { code: 'request_failed', message: 'private-marker' },
      }),
      false,
    ),
    { kind: 'submitting', message: 'Submitting prompt…' },
  )
})

test('controlled non-live success fixture is preserved as plain response text', () => {
  const controlledNonLiveFixture = 'Controlled non-live fixture response. <b>text only</b>'
  assert.deepEqual(
    getChatView(chat({ response: controlledNonLiveFixture }), false),
    { kind: 'success', response: controlledNonLiveFixture },
  )
})

test('configuration and dependency errors use fixed safe messages', () => {
  const cases = [
    [
      'service_unavailable',
      {
        kind: 'unavailable',
        message: 'AgentPod is not configured or its dependency is unavailable.',
      },
    ],
    [
      'service_timeout',
      { kind: 'dependency-error', message: 'The AgentPod dependency timed out.' },
    ],
    [
      'service_error',
      {
        kind: 'dependency-error',
        message: 'The AgentPod dependency could not complete the request.',
      },
    ],
  ]

  for (const [code, expected] of cases) {
    const view = getChatView(
      chat({ error: { code, message: 'private-host-prompt-marker' } }),
      false,
    )
    assert.deepEqual(view, expected)
    assert.doesNotMatch(JSON.stringify(view), /private-host-prompt-marker/)
  }
})

test('unexpected errors use one generic failure without raw detail', () => {
  const view = getChatView(
    chat({
      error: {
        code: 'network_error',
        message: 'private-network-and-prompt-marker',
      },
    }),
    false,
  )
  assert.deepEqual(view, {
    kind: 'failure',
    message: 'AgentPod could not complete the request.',
  })
  assert.doesNotMatch(JSON.stringify(view), /private-network|prompt-marker/)
})
