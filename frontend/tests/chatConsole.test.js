import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { compileTemplate, parse } from '@vue/compiler-sfc'

const componentUrl = new URL('../src/components/ChatConsole.vue', import.meta.url)
const appUrl = new URL('../src/App.vue', import.meta.url)

async function descriptor(url, filename) {
  const source = await readFile(url, 'utf8')
  const parsed = parse(source, { filename })
  assert.deepEqual(parsed.errors, [])
  assert(parsed.descriptor.scriptSetup)
  assert(parsed.descriptor.template)
  return { source, descriptor: parsed.descriptor }
}

test('chat template compiles with accessible prompt and public states', async () => {
  const { source, descriptor: component } = await descriptor(componentUrl, 'ChatConsole.vue')
  const compiled = compileTemplate({
    source: component.template.content,
    filename: 'ChatConsole.vue',
    id: 'chat-console-test',
  })
  assert.deepEqual(compiled.errors, [])

  const template = component.template.content
  assert.match(template, /aria-labelledby="chat-heading"/)
  assert.match(template, /<label[^>]+for="agentpod-prompt"/)
  assert.match(template, /<textarea/)
  assert.match(template, /:aria-invalid=/)
  assert.match(template, /role="alert"/)
  assert.match(template, /role="status"/)
  assert.match(template, /aria-live="polite"/)
  assert.match(template, /data-state="submitting"/)
  assert.match(template, /data-state="success"/)
  assert.match(template, /\{\{ view\.response \}\}/)
  assert.match(template, /:disabled="chat\.loading"/)

  assert.doesNotMatch(template, /v-html|innerHTML|markdown/i)
  assert.doesNotMatch(
    source,
    /fetch\s*\(|console\.|retry|history|stream|modelPicker|selectedModel|modelName/i,
  )
})

test('submission guards blanks and duplicate submits and calls state once', async () => {
  const { source } = await descriptor(componentUrl, 'ChatConsole.vue')
  assert.match(source, /if \(chat\.loading\)/)
  assert.match(source, /prompt\.value\.trim\(\)\.length === 0/)
  assert.match(source, /await submitChat\(prompt\.value\)/)
  assert.doesNotMatch(source, /setTimeout|setInterval/)
})

test('root shell mounts one prompt console without router or store', async () => {
  const { source, descriptor: app } = await descriptor(appUrl, 'App.vue')
  assert.match(source, /import ChatConsole/)
  assert.equal((app.template.content.match(/<ChatConsole\s*\/>/g) ?? []).length, 1)
  assert.doesNotMatch(source, /router|pinia|fetch\s*\(/i)
})
