export function appendReactiveMessage(messages, message) {
  messages.push(message)
  return messages[messages.length - 1]
}
