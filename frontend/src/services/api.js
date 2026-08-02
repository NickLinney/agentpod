const ERROR_MESSAGES = Object.freeze({
  invalid_request: 'The request was invalid.',
  service_error: 'AgentPod could not complete the request.',
  service_unavailable: 'AgentPod is unavailable.',
  service_timeout: 'AgentPod timed out.',
  network_error: 'AgentPod could not be reached.',
  invalid_response: 'AgentPod returned an invalid response.',
  request_failed: 'AgentPod request failed.',
})

const STATUS_ERROR_CODES = Object.freeze({
  422: 'invalid_request',
  502: 'service_error',
  503: 'service_unavailable',
  504: 'service_timeout',
})

export class ApiServiceError extends Error {
  constructor(code) {
    const safeCode = Object.hasOwn(ERROR_MESSAGES, code) ? code : 'request_failed'
    super(ERROR_MESSAGES[safeCode])
    this.name = 'ApiServiceError'
    this.code = safeCode
  }
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function invalidResponse() {
  return new ApiServiceError('invalid_response')
}

async function readJson(response) {
  try {
    return await response.json()
  } catch {
    throw invalidResponse()
  }
}

async function requestJson(fetchImplementation, path, options) {
  let response
  try {
    response = await fetchImplementation(path, options)
  } catch {
    throw new ApiServiceError('network_error')
  }

  if (!response || typeof response.ok !== 'boolean') {
    throw invalidResponse()
  }
  if (!response.ok) {
    throw new ApiServiceError(STATUS_ERROR_CODES[response.status] ?? 'request_failed')
  }
  return readJson(response)
}

function parseHealth(payload) {
  if (!isRecord(payload) || payload.status !== 'healthy') {
    throw invalidResponse()
  }
  return Object.freeze({ status: 'healthy' })
}

function parseStatus(payload) {
  const dependency = payload?.dependencies?.ollama
  if (
    !isRecord(payload) ||
    !['ready', 'degraded'].includes(payload.status) ||
    !isRecord(payload.dependencies) ||
    !isRecord(dependency) ||
    typeof dependency.configured !== 'boolean' ||
    typeof dependency.ready !== 'boolean' ||
    typeof dependency.detail !== 'string' ||
    dependency.detail.length === 0
  ) {
    throw invalidResponse()
  }

  return Object.freeze({
    status: payload.status,
    dependencies: Object.freeze({
      ollama: Object.freeze({
        configured: dependency.configured,
        ready: dependency.ready,
        detail: dependency.detail,
      }),
    }),
  })
}

function parseChat(payload) {
  if (
    !isRecord(payload) ||
    typeof payload.response !== 'string' ||
    payload.response.trim().length === 0
  ) {
    throw invalidResponse()
  }
  return Object.freeze({ response: payload.response })
}

export function createApiService(fetchImplementation = globalThis.fetch) {
  if (typeof fetchImplementation !== 'function') {
    throw new ApiServiceError('network_error')
  }

  return Object.freeze({
    async getHealth() {
      const payload = await requestJson(fetchImplementation, '/api/health', {
        method: 'GET',
        headers: { Accept: 'application/json' },
      })
      return parseHealth(payload)
    },

    async getStatus() {
      const payload = await requestJson(fetchImplementation, '/api/status', {
        method: 'GET',
        headers: { Accept: 'application/json' },
      })
      return parseStatus(payload)
    },

    async sendChat(message) {
      const payload = await requestJson(fetchImplementation, '/api/chat', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
      })
      return parseChat(payload)
    },
  })
}

const defaultService = createApiService()

export const getHealth = defaultService.getHealth
export const getStatus = defaultService.getStatus
export const sendChat = defaultService.sendChat

export function toPublicError(error) {
  const safeError =
    error instanceof ApiServiceError ? error : new ApiServiceError('request_failed')
  return Object.freeze({ code: safeError.code, message: safeError.message })
}
