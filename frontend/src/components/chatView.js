const IDLE_VIEW = Object.freeze({ kind: 'idle' })
const SUBMITTING_VIEW = Object.freeze({
  kind: 'submitting',
  message: 'Submitting prompt…',
})
const BLANK_VIEW = Object.freeze({
  kind: 'invalid',
  message: 'Enter a prompt before submitting.',
})
const UNAVAILABLE_VIEW = Object.freeze({
  kind: 'unavailable',
  message: 'AgentPod is not configured or its dependency is unavailable.',
})
const TIMEOUT_VIEW = Object.freeze({
  kind: 'dependency-error',
  message: 'The AgentPod dependency timed out.',
})
const DEPENDENCY_ERROR_VIEW = Object.freeze({
  kind: 'dependency-error',
  message: 'The AgentPod dependency could not complete the request.',
})
const GENERIC_FAILURE_VIEW = Object.freeze({
  kind: 'failure',
  message: 'AgentPod could not complete the request.',
})

export function getChatView(chat, blankInvalid) {
  if (blankInvalid) {
    return BLANK_VIEW
  }
  if (chat.loading) {
    return SUBMITTING_VIEW
  }
  if (typeof chat.response === 'string') {
    return Object.freeze({ kind: 'success', response: chat.response })
  }

  switch (chat.error?.code) {
    case 'invalid_request':
      return BLANK_VIEW
    case 'service_unavailable':
      return UNAVAILABLE_VIEW
    case 'service_timeout':
      return TIMEOUT_VIEW
    case 'service_error':
      return DEPENDENCY_ERROR_VIEW
    default:
      return chat.error ? GENERIC_FAILURE_VIEW : IDLE_VIEW
  }
}
