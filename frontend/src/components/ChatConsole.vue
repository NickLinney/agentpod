<script setup>
import { computed, ref } from 'vue'

import { useAgentPodState } from '../composables/useAgentPodState.js'
import { getChatView } from './chatView.js'

const prompt = ref('')
const blankInvalid = ref(false)
const { chat, submitChat } = useAgentPodState()
const view = computed(() => getChatView(chat, blankInvalid.value))

async function submitPrompt() {
  if (chat.loading) {
    return
  }
  if (prompt.value.trim().length === 0) {
    blankInvalid.value = true
    return
  }

  blankInvalid.value = false
  await submitChat(prompt.value)
}
</script>

<template>
  <section class="box" aria-labelledby="chat-heading">
    <h2 id="chat-heading" class="title is-4">Conversation</h2>

    <form @submit.prevent="submitPrompt" novalidate>
      <div class="field">
        <label class="label" for="agentpod-prompt">Prompt</label>
        <div class="control">
          <textarea
            id="agentpod-prompt"
            v-model="prompt"
            class="textarea"
            :class="{ 'is-danger': view.kind === 'invalid' }"
            :aria-invalid="view.kind === 'invalid'"
            :aria-describedby="view.kind === 'invalid' ? 'prompt-error' : undefined"
            :disabled="chat.loading"
            rows="5"
          />
        </div>
        <p v-if="view.kind === 'invalid'" id="prompt-error" class="help is-danger" role="alert">
          {{ view.message }}
        </p>
      </div>

      <div class="field">
        <div class="control">
          <button
            class="button is-info"
            :class="{ 'is-loading': chat.loading }"
            :disabled="chat.loading"
            type="submit"
          >
            Submit
          </button>
        </div>
      </div>
    </form>

    <div
      v-if="view.kind === 'submitting'"
      class="notification is-light"
      role="status"
      aria-live="polite"
      data-state="submitting"
    >
      {{ view.message }}
    </div>

    <div
      v-else-if="view.kind === 'success'"
      class="notification is-success is-light"
      aria-live="polite"
      data-state="success"
    >
      <p class="heading">Response</p>
      <p class="response-text">{{ view.response }}</p>
    </div>

    <div
      v-else-if="['unavailable', 'dependency-error', 'failure'].includes(view.kind)"
      class="notification is-danger is-light"
      role="alert"
      data-state="failure"
    >
      {{ view.message }}
    </div>
  </section>
</template>

<style scoped>
.response-text {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
</style>
