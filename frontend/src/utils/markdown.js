import MarkdownIt from 'markdown-it'

// html: false —— 把回复中可能夹带的原始 HTML 标签转义为文本，从根上避免 v-html 注入风险。
// breaks: true —— 聊天回复常用单换行分段，开这个让单换行也正常换行，更贴近对话体。
const md = new MarkdownIt({
  html: false,
  linkify: false,
  breaks: true,
  typographer: false
})

const defaultLinkOpen =
  md.renderer.rules.link_open ||
  function (tokens, idx, options, env, self) {
    return self.renderToken(tokens, idx, options, env, self)
  }

// 收紧链接：只放行 http/https/mailto/锚点/站内相对路径，其余（如 javascript:）一律降级为 "#"，
// 并统一新窗口打开 + 去除 referrer，避免外链通过 window.opener 反向操作本页。
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const href = tokens[idx].attrGet('href')
  if (href && !/^(https?:|mailto:|#|\/)/i.test(href)) {
    tokens[idx].attrSet('href', '#')
  }
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

export function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text)
}
