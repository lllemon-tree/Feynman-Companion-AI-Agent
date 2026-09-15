import assert from 'node:assert/strict'
import test from 'node:test'
import { isReactive, reactive, watch } from 'vue'
import { appendReactiveMessage } from '../src/utils/reactiveMessage.js'

test('knowledge-point reply deltas update the visible reactive message immediately', () => {
  const messages = reactive([])
  const pending = appendReactiveMessage(messages, { role: 'ai', content: '' })
  const visibleChanges = []
  const stop = watch(
    () => messages.at(-1)?.content,
    content => visibleChanges.push(content),
    { flush: 'sync' }
  )
  try {
    assert.equal(isReactive(pending), true)
    pending.content += '第一段'
    pending.content += '第二段'
    assert.deepEqual(visibleChanges, ['第一段', '第一段第二段'])
  } finally {
    stop()
  }
})
