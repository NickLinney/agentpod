import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { compileTemplate, parse } from '@vue/compiler-sfc'

const componentUrl = new URL('../src/components/StatusDashboard.vue', import.meta.url)
const appUrl = new URL('../src/App.vue', import.meta.url)

async function descriptor(url, filename) {
  const source = await readFile(url, 'utf8')
  const parsed = parse(source, { filename })
  assert.deepEqual(parsed.errors, [])
  assert(parsed.descriptor.scriptSetup)
  assert(parsed.descriptor.template)
  return { source, descriptor: parsed.descriptor }
}

test('dashboard template compiles and exposes accessible public states', async () => {
  const { source, descriptor: component } = await descriptor(
    componentUrl,
    'StatusDashboard.vue',
  )
  const compiled = compileTemplate({
    source: component.template.content,
    filename: 'StatusDashboard.vue',
    id: 'status-dashboard-test',
  })
  assert.deepEqual(compiled.errors, [])

  const template = component.template.content
  assert.match(template, /aria-labelledby="status-heading"/)
  assert.match(template, /id="status-heading"/)
  assert.match(template, /role="status"/)
  assert.match(template, /aria-live="polite"/)
  assert.match(template, /data-state="loading"/)
  assert.match(template, /role="alert"/)
  assert.match(template, /data-state="failure"/)
  assert.match(template, /:data-state="view\.healthState"/)
  assert.match(template, /:data-state="view\.readinessState"/)
  assert.match(template, /Loading AgentPod status/)
  assert.match(template, /AgentPod status is currently unavailable/)
  assert.match(template, />Health</)
  assert.match(template, />Readiness</)

  assert.doesNotMatch(template, /error\.message|error\.code/)
  assert.doesNotMatch(source, /fetch\s*\(/)
  assert.doesNotMatch(template, /model|metrics/i)
})

test('root shell contains the dashboard without router or store surface', async () => {
  const { source, descriptor: app } = await descriptor(appUrl, 'App.vue')
  assert.match(source, /import StatusDashboard/)
  assert.match(app.template.content, /<StatusDashboard\s*\/>/)
  assert.match(app.template.content, /<main class="section">/)
  assert.doesNotMatch(source, /router|pinia|fetch\s*\(/i)
})
