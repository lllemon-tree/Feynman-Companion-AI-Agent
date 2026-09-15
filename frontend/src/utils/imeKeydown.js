/** Enter may mean "confirm this IME candidate", not "send this message". */
export function enterAction(event, composing, compositionEndedAt, now = performance.now()) {
  if (event.key !== 'Enter') return 'none'
  if (event.isComposing || composing || event.keyCode === 229) return 'compose'
  // Safari/Chrome can emit compositionend before the confirming Enter keydown.
  if (now - compositionEndedAt < 80) return 'skip'
  return event.shiftKey ? 'newline' : 'send'
}
