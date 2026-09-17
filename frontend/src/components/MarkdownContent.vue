<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
})

const html = computed(() => renderMarkdown(props.content))
</script>

<template>
  <div class="markdown-body" v-html="html"></div>
</template>

<style scoped>
.markdown-body {
  color: inherit;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.markdown-body :deep(p) { margin: 0 0 8px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(strong) { font-weight: 600; }
.markdown-body :deep(em) { font-style: italic; }

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 14px 0 6px;
  line-height: 1.4;
  font-weight: 650;
  color: inherit;
}
.markdown-body :deep(h1) { font-size: 19px; }
.markdown-body :deep(h2) { font-size: 17px; }
.markdown-body :deep(h3) { font-size: 15px; }
.markdown-body :deep(h4) { font-size: 14px; }
.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child),
.markdown-body :deep(h4:first-child) {
  margin-top: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}
.markdown-body :deep(li) { margin-bottom: 4px; }
.markdown-body :deep(li:last-child) { margin-bottom: 0; }

.markdown-body :deep(blockquote) {
  margin: 10px 0;
  padding: 4px 0 4px 12px;
  border-left: 3px solid #cbd5e1;
  color: #64748b;
}

.markdown-body :deep(pre) {
  margin: 10px 0;
  padding: 12px 14px;
  background: #0f172a;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre;
}
.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #e2e8f0;
}

.markdown-body :deep(:not(pre) > code) {
  padding: 1px 5px;
  background: #eef2f7;
  border-radius: 4px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', Menlo, Consolas, monospace;
  font-size: 0.88em;
  color: #b45309;
}

.markdown-body :deep(a) { color: #2563eb; text-decoration: none; }
.markdown-body :deep(a:hover) { text-decoration: underline; }

.markdown-body :deep(table) {
  margin: 10px 0;
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  text-align: left;
}
.markdown-body :deep(th) { background: #f1f5f9; font-weight: 600; }

.markdown-body :deep(hr) {
  margin: 14px 0;
  border: 0;
  border-top: 1px solid #e2e8f0;
}
</style>
