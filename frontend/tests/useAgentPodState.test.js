import assert from 'node:assert/strict'
import test from 'node:test'

import { ApiServiceError } from '../src/services/api.js'
import { useAgentPodState } from '../src/composables/useAgentPodState.js'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function service(overrides = {}) {
  return {
    async getHealth() {
      return { status: 'healthy' }
    },
    async getStatus() {
      return { status: 'degraded' }
    },
    async sendChat() {
      return { response: 'response' }
    },
    ...overrides,
  }
}

test('initial local interaction state is empty and not loading', () => {
  const state = useAgentPodState(service())
  assert.deepEqual({ ...state.health }, { loading: false, data: null, error: null })
  assert.deepEqual({ ...state.status }, { loading: false, data: null, error: null })
  assert.deepEqual(
    { ...state.chat },
    { loading: false, response: null, error: null },
  )
})

test('health lifecycle stores only successful service data', async () => {
  const pending = deferred()
  let calls = 0
  const state = useAgentPodState(service({
    getHealth() {
      calls += 1
      return pending.promise
    },
  }))

  const request = state.refreshHealth()
  assert.equal(state.health.loading, true)
  assert.equal(state.health.data, null)
  assert.equal(state.health.error, null)

  pending.resolve({ status: 'healthy' })
  assert.deepEqual(await request, { status: 'healthy' })
  assert.equal(calls, 1)
  assert.equal(state.health.loading, false)
  assert.deepEqual(state.health.data, { status: 'healthy' })
  assert.equal(state.health.error, null)
})

test('status failure becomes fixed local state without retry or raw error', async () => {
  let calls = 0
  const state = useAgentPodState(service({
    async getStatus() {
      calls += 1
      throw new ApiServiceError('service_unavailable')
    },
  }))

  assert.equal(await state.refreshStatus(), null)
  assert.equal(calls, 1)
  assert.equal(state.status.loading, false)
  assert.equal(state.status.data, null)
  assert.deepEqual(state.status.error, {
    code: 'service_unavailable',
    message: 'AgentPod is unavailable.',
  })
})

test('chat lifecycle preserves exact response and clears prior safe error', async () => {
  let calls = 0
  const state = useAgentPodState(service({
    async sendChat(message) {
      calls += 1
      assert.equal(message, ' original prompt ')
      return { response: ' exact response ' }
    },
  }))
  state.chat.error = { code: 'request_failed', message: 'AgentPod request failed.' }

  const result = await state.submitChat(' original prompt ')
  assert.equal(calls, 1)
  assert.deepEqual(result, { response: ' exact response ' })
  assert.equal(state.chat.loading, false)
  assert.equal(state.chat.response, ' exact response ')
  assert.equal(state.chat.error, null)
})

test('unexpected chat errors are discarded and replaced by fixed state', async () => {
  let calls = 0
  const state = useAgentPodState(service({
    async sendChat() {
      calls += 1
      throw new Error('private-chat-marker')
    },
  }))

  assert.equal(await state.submitChat('message'), null)
  assert.equal(calls, 1)
  assert.equal(state.chat.loading, false)
  assert.equal(state.chat.response, null)
  assert.deepEqual(state.chat.error, {
    code: 'request_failed',
    message: 'AgentPod request failed.',
  })
  assert.doesNotMatch(JSON.stringify(state.chat.error), /private-chat-marker/)
})
