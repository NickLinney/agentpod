import { reactive } from 'vue'

import {
  getHealth,
  getStatus,
  sendChat,
  toPublicError,
} from '../services/api.js'

const defaultService = Object.freeze({ getHealth, getStatus, sendChat })

function createResourceState() {
  return reactive({ loading: false, data: null, error: null })
}

export function useAgentPodState(service = defaultService) {
  const health = createResourceState()
  const status = createResourceState()
  const chat = reactive({ loading: false, response: null, error: null })

  async function loadResource(state, request) {
    state.loading = true
    state.data = null
    state.error = null
    try {
      const data = await request()
      state.data = data
      return data
    } catch (error) {
      state.error = toPublicError(error)
      return null
    } finally {
      state.loading = false
    }
  }

  function refreshHealth() {
    return loadResource(health, service.getHealth)
  }

  function refreshStatus() {
    return loadResource(status, service.getStatus)
  }

  async function submitChat(message) {
    chat.loading = true
    chat.response = null
    chat.error = null
    try {
      const result = await service.sendChat(message)
      chat.response = result.response
      return result
    } catch (error) {
      chat.error = toPublicError(error)
      return null
    } finally {
      chat.loading = false
    }
  }

  return Object.freeze({
    health,
    status,
    chat,
    refreshHealth,
    refreshStatus,
    submitChat,
  })
}
