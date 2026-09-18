export function historyModeForPath(path) {
  if (path === '/home') return 'conversation'
  if (path === '/select' || path === '/study') return 'knowledge'
  return null
}

export function normalizeHistoryItems(mode, items = []) {
  if (mode === 'knowledge') {
    return items.map(item => ({
      id: item.session_id,
      title: item.kp_name || '未命名知识点',
      subtitle: item.material_title || '',
      route: { path: '/study', query: { sessionId: item.session_id } }
    }))
  }
  if (mode === 'conversation') {
    return items.map(item => ({
      id: item.id,
      title: item.title || '未命名对话',
      subtitle: '',
      route: { path: '/home', query: { conversation: item.id } }
    }))
  }
  return []
}
