import { test } from 'node:test'
import assert from 'node:assert/strict'
import { enterAction } from '../src/utils/imeKeydown.js'

test('Enter selecting a Chinese IME candidate never sends', () => {
  assert.equal(enterAction({ key: 'Enter', isComposing: true }, false, 0, 1000), 'compose')
  assert.equal(enterAction({ key: 'Enter' }, true, 0, 1000), 'compose')
  assert.equal(enterAction({ key: 'Enter', keyCode: 229 }, false, 0, 1000), 'compose')
  assert.equal(enterAction({ key: 'Enter' }, false, 980, 1000), 'skip')
})

test('ordinary Enter sends and Shift+Enter inserts a newline', () => {
  assert.equal(enterAction({ key: 'Enter' }, false, 0, 1000), 'send')
  assert.equal(enterAction({ key: 'Enter', shiftKey: true }, false, 0, 1000), 'newline')
  assert.equal(enterAction({ key: 'a' }, false, 0, 1000), 'none')
})
