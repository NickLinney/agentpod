import assert from 'node:assert/strict'
import test from 'node:test'

import {
  ApiServiceError,
  createApiService,
  toPublicError,
} from '../src/services/api.js'

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return payload
    },
  }
}

test('getHealth uses only the approved endpoint and normalizes its payload', async () => {
  const calls = []
  const service = createApiService(async (...args) => {
    calls.push(args)
    return jsonResponse({ status: 'healthy', ignored: 'private-marker' })
  })

  assert.deepEqual(await service.getHealth(), { status: 'healthy' })
  assert.deepEqual(calls, [
    ['/api/health', { method: 'GET', headers: { Accept: 'application/json' } }],
  ])
})

test('getStatus uses only the approved endpoint and strips unknown fields', async () => {
  const calls = []
  const service = createApiService(async (...args) => {
    calls.push(args)
    return jsonResponse({
      status: 'degraded',
      dependencies: {
        ollama: {
          configured: false,
          ready: false,
          detail: 'configuration_incomplete',
          private: 'private-marker',
        },
      },
      private: 'private-marker',
    })
  })

  assert.deepEqual(await service.getStatus(), {
    status: 'degraded',
    dependencies: {
      ollama: {
        configured: false,
        ready: false,
        detail: 'configuration_incomplete',
      },
    },
  })
  assert.deepEqual(calls, [
    ['/api/status', { method: 'GET', headers: { Accept: 'application/json' } }],
  ])
})

test('sendChat posts the original message once and preserves the response', async () => {
  const calls = []
  const service = createApiService(async (...args) => {
    calls.push(args)
    return jsonResponse({ response: ' exact assistant response ' })
  })

  assert.deepEqual(await service.sendChat(' original message '), {
    response: ' exact assistant response ',
  })
  assert.deepEqual(calls, [
    [
      '/api/chat',
      {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: ' original message ' }),
      },
    ],
  ])
})

test('fixed HTTP status mappings never parse or expose raw error bodies', async () => {
  const cases = [
    [422, 'invalid_request'],
    [502, 'service_error'],
    [503, 'service_unavailable'],
    [504, 'service_timeout'],
    [500, 'request_failed'],
  ]

  for (const [status, code] of cases) {
    let parseCount = 0
    const service = createApiService(async () => ({
      ok: false,
      status,
      async json() {
        parseCount += 1
        return { detail: 'private-upstream-marker' }
      },
    }))

    await assert.rejects(service.sendChat('message'), (error) => {
      assert(error instanceof ApiServiceError)
      assert.equal(error.code, code)
      assert.doesNotMatch(error.message, /private-upstream-marker/)
      return true
    })
    assert.equal(parseCount, 0)
  }
})

test('network failures map to a fixed error without retry or raw detail', async () => {
  let calls = 0
  const service = createApiService(async () => {
    calls += 1
    throw new Error('private-network-marker')
  })

  await assert.rejects(service.getHealth(), (error) => {
    assert(error instanceof ApiServiceError)
    assert.equal(error.code, 'network_error')
    assert.doesNotMatch(error.message, /private-network-marker/)
    assert.doesNotMatch(error.stack, /private-network-marker/)
    return true
  })
  assert.equal(calls, 1)
})

test('malformed successful responses use only the fixed invalid-response error', async () => {
  const malformedResponses = [
    { ok: true, status: 200, async json() { throw new Error('private-json-marker') } },
    jsonResponse(null),
    jsonResponse({ status: 'unknown' }),
    jsonResponse({ response: '   ' }),
  ]

  for (const response of malformedResponses) {
    const service = createApiService(async () => response)
    await assert.rejects(service.sendChat('message'), (error) => {
      assert(error instanceof ApiServiceError)
      assert.equal(error.code, 'invalid_response')
      assert.doesNotMatch(error.message, /private/)
      return true
    })
  }
})

test('toPublicError emits a fixed frozen value and discards unknown errors', () => {
  const known = toPublicError(new ApiServiceError('service_timeout'))
  assert.deepEqual(known, {
    code: 'service_timeout',
    message: 'AgentPod timed out.',
  })
  assert(Object.isFrozen(known))

  const unknown = toPublicError(new Error('private-state-marker'))
  assert.deepEqual(unknown, {
    code: 'request_failed',
    message: 'AgentPod request failed.',
  })
  assert.doesNotMatch(JSON.stringify(unknown), /private-state-marker/)
})
