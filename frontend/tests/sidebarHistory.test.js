import test from 'node:test'
import assert from 'node:assert/strict'

import { historyModeForPath, normalizeHistoryItems } from '../src/utils/sidebarHistory.js'


test('selects recent conversations from the active learning module', () => {
  assert.equal(historyModeForPath('/home'), 'conversation')
  assert.equal(historyModeForPath('/select'), 'knowledge')
  assert.equal(historyModeForPath('/study'), 'knowledge')
  assert.equal(historyModeForPath('/profile'), null)
})

test('normalizes knowledge sessions into study routes', () => {
  const items = normalizeHistoryItems('knowledge', [
    {
      session_id: 'session-1',
      kp_name: '二叉树遍历',
      material_title: '数据结构',
      created_at: '2026-09-18T10:00:00Z'
    }
  ])

  assert.deepEqual(items, [{
    id: 'session-1',
    title: '二叉树遍历',
    subtitle: '数据结构',
    route: { path: '/study', query: { sessionId: 'session-1' } }
  }])
})

test('normalizes free conversations into home routes', () => {
  const items = normalizeHistoryItems('conversation', [
    { id: 'conversation-1', title: '解释递归' }
  ])

  assert.deepEqual(items, [{
    id: 'conversation-1',
    title: '解释递归',
    subtitle: '',
    route: { path: '/home', query: { conversation: 'conversation-1' } }
  }])
})
