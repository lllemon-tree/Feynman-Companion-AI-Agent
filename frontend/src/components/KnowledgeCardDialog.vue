<script setup>
defineProps({
  open: { type: Boolean, default: false },
  card: { type: Object, default: null },
  fallbackName: { type: String, default: '' },
  fallbackSummary: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  favoriteSaving: { type: Boolean, default: false },
  showFavorite: { type: Boolean, default: true },
  primaryLabel: { type: String, default: '开始费曼讲解' },
  footerText: { type: String, default: '读完后，用自己的话讲给“小白”听。' }
})

defineEmits(['close', 'retry', 'toggle-favorite', 'primary'])

function sourceLabel(type) {
  return {
    textbook: '教材原文',
    textbook_rewrite: '教材内容通俗解释',
    model_supplement: '补充理解'
  }[type] || '内容说明'
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="card-overlay" @click.self="$emit('close')">
      <section class="knowledge-card-dialog" role="dialog" aria-modal="true" aria-label="知识卡片">
        <header class="card-header">
          <div>
            <span class="card-eyebrow">知识输入 · {{ card?.estimated_minutes || 5 }} 分钟</span>
            <h2>{{ card?.name || fallbackName }}</h2>
            <p>{{ card?.summary || fallbackSummary }}</p>
          </div>
          <div class="card-header-actions">
            <button
              v-if="showFavorite && card"
              type="button"
              class="favorite-btn"
              :class="{ 'favorite-btn--active': card.is_favorited }"
              :disabled="favoriteSaving"
              @click="$emit('toggle-favorite')"
            >
              <span aria-hidden="true">{{ card.is_favorited ? '★' : '☆' }}</span>
              {{ favoriteSaving ? '处理中' : card.is_favorited ? '已收藏' : '收藏' }}
            </button>
            <button type="button" class="card-close" aria-label="关闭" @click="$emit('close')">×</button>
          </div>
        </header>

        <div class="card-body">
          <div v-if="loading" class="card-loading">
            <span class="card-spinner"></span>
            <strong>正在载入教材基础卡片…</strong>
            <p>基础内容就绪后会立即展示，模型增强将在后台继续完成。</p>
          </div>
          <div v-else-if="error" class="card-error">
            <strong>知识卡片暂时未准备好</strong>
            <p>{{ error }}</p>
            <button type="button" @click="$emit('retry')">重试</button>
          </div>
          <template v-else-if="card">
            <div v-if="card.generation_status === 'generating'" class="enhancement-note enhancement-note--loading">
              <span class="enhancement-dot"></span>
              <div>
                <strong>教材基础卡片已就绪</strong>
                <p>正在补充通俗解释、示例与误区，你可以先阅读当前内容。</p>
              </div>
            </div>
            <div v-else-if="card.generation_status === 'failed'" class="enhancement-note enhancement-note--failed">
              <div>
                <strong>模型增强暂未完成</strong>
                <p>当前内容仍来自教材和评分基准，可以正常开始学习；下次打开时会自动重试。</p>
              </div>
            </div>
            <div class="coverage-note" :class="`coverage-note--${card.coverage_level}`">
              <strong>{{ card.coverage_level === 'sufficient' ? '教材依据较完整' : card.coverage_level === 'partial' ? '教材依据部分覆盖' : '教材依据有限' }}</strong>
              <span>{{ card.coverage_notice }}</span>
            </div>
            <article v-for="section in card.sections" :key="section.key" class="card-section">
              <div class="card-section-heading">
                <h3>{{ section.title }}</h3>
                <span class="source-badge" :class="`source-badge--${section.source_type}`">{{ sourceLabel(section.source_type) }}</span>
              </div>
              <p v-if="section.content" class="section-content">{{ section.content }}</p>
              <ul v-if="section.bullets?.length">
                <li v-for="(item, index) in section.bullets" :key="index">{{ item }}</li>
              </ul>
              <p v-if="section.source_type === 'model_supplement'" class="supplement-hint">这部分用于帮助理解，不作为诊断必答项。</p>
            </article>
            <details v-if="card.sources?.length" class="source-details">
              <summary>查看教材依据（{{ card.sources.length }} 处）</summary>
              <div v-for="source in card.sources" :key="source.chunk_id" class="source-item">
                <strong>第 {{ source.page }} 页</strong>
                <p>{{ source.excerpt }}</p>
              </div>
            </details>
          </template>
        </div>

        <footer class="card-footer">
          <span>{{ footerText }}</span>
          <button type="button" class="explain-btn" :disabled="loading" @click="$emit('primary')">
            {{ primaryLabel }} <span aria-hidden="true">→</span>
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.card-overlay { position: fixed; inset: 0; z-index: 300; display: grid; place-items: center; padding: 24px; background: rgba(17, 30, 55, .55); }
.knowledge-card-dialog { width: min(860px, 100%); max-height: min(90dvh, 920px); display: flex; flex-direction: column; overflow: hidden; border-radius: 20px; background: #fff; box-shadow: 0 30px 90px rgba(15, 31, 60, .25); }
.card-header { display: flex; justify-content: space-between; gap: 20px; padding: 26px 30px 20px; border-bottom: 1px solid #e8edf5; }
.card-eyebrow { color: #3267d8; font-size: 11px; font-weight: 750; letter-spacing: .08em; }
.card-header h2 { margin: 8px 0 6px; color: #17233b; font-size: 25px; }
.card-header p { margin: 0; color: #718198; font-size: 13px; line-height: 1.6; }
.card-close { width: 34px; height: 34px; flex: none; border: 1px solid #e1e7f0; border-radius: 10px; background: #fff; color: #6b7a91; font-size: 24px; }
.card-header-actions { display: flex; align-items: center; gap: 9px; flex: none; }
.favorite-btn { min-height: 34px; display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; border: 1px solid #d9e2f0; border-radius: 9px; color: #66758c; background: #fff; font-size: 12px; font-weight: 650; }
.favorite-btn:hover { color: #245fd4; border-color: #a9c2f4; background: #f7faff; }
.favorite-btn--active { color: #b76a00; border-color: #f0ca83; background: #fff8e8; }
.favorite-btn:disabled { opacity: .55; cursor: wait; }
.card-body { min-height: 250px; overflow-y: auto; padding: 24px 30px 28px; }
.card-loading, .card-error { min-height: 260px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: #65758d; text-align: center; }
.card-loading p, .card-error p { margin: 0; color: #93a0b2; font-size: 12px; }
.card-error button { padding: 8px 15px; border-radius: 8px; color: #245fd4; background: #edf3ff; }
.card-spinner { width: 28px; height: 28px; border: 3px solid #dce8ff; border-top-color: #2e68de; border-radius: 50%; animation: card-spin .8s linear infinite; }
@keyframes card-spin { to { transform: rotate(360deg); } }
.enhancement-note { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px; padding: 12px 14px; border-radius: 11px; }
.enhancement-note strong { display: block; margin-bottom: 3px; font-size: 13px; }
.enhancement-note p { margin: 0; font-size: 12px; line-height: 1.6; }
.enhancement-note--loading { color: #2858b8; background: #edf4ff; }
.enhancement-note--failed { color: #8a5a18; background: #fff7e8; }
.enhancement-dot { width: 8px; height: 8px; flex: none; margin-top: 5px; border-radius: 50%; background: #3478ed; box-shadow: 0 0 0 4px rgba(52, 120, 237, .12); animation: enhancement-pulse 1.2s ease-in-out infinite; }
@keyframes enhancement-pulse { 50% { opacity: .35; transform: scale(.8); } }
.coverage-note { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; margin-bottom: 18px; border-radius: 11px; background: #f4f8ff; color: #4d6384; font-size: 12px; line-height: 1.55; }
.coverage-note strong { flex: none; color: #2e62c9; }
.coverage-note--limited { background: #fff8ed; }
.coverage-note--limited strong { color: #a56825; }
.card-section { padding: 18px 0; border-bottom: 1px solid #edf1f6; }
.card-section:last-of-type { border-bottom: 0; }
.card-section-heading { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.card-section h3 { margin: 0; color: #21334f; font-size: 16px; }
.source-badge { padding: 3px 7px; border-radius: 6px; background: #eaf2ff; color: #3467ca; font-size: 10px; font-weight: 650; }
.source-badge--model_supplement { background: #f1edff; color: #7254bc; }
.source-badge--textbook { background: #ecf8f2; color: #318260; }
.section-content { margin: 0; color: #445873; font-size: 14px; line-height: 1.85; white-space: pre-wrap; }
.card-section ul { margin: 0; padding-left: 20px; color: #445873; font-size: 14px; line-height: 1.8; }
.card-section li + li { margin-top: 5px; }
.supplement-hint { margin: 10px 0 0; color: #8b79b7; font-size: 11px; }
.source-details { margin-top: 18px; padding: 13px 15px; border-radius: 10px; background: #f7f9fc; color: #65758d; font-size: 12px; }
.source-details summary { cursor: pointer; font-weight: 650; color: #50627d; }
.source-item { padding-top: 11px; margin-top: 11px; border-top: 1px solid #e3e9f1; }
.source-item p { margin: 4px 0 0; line-height: 1.65; }
.card-footer { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 17px 30px; border-top: 1px solid #e8edf5; background: #fbfcff; }
.card-footer > span { color: #8795a9; font-size: 12px; }
.explain-btn { display: inline-flex; align-items: center; gap: 9px; padding: 11px 18px; border-radius: 10px; background: #2764df; color: #fff; font-size: 14px; font-weight: 650; }
.explain-btn:disabled { opacity: .55; cursor: wait; }
@media (max-width: 680px) {
  .card-overlay { padding: 0; align-items: end; }
  .knowledge-card-dialog { max-height: 96dvh; border-radius: 18px 18px 0 0; }
  .card-header, .card-body { padding-left: 18px; padding-right: 18px; }
  .card-footer { align-items: stretch; flex-direction: column; padding: 14px 18px; }
  .explain-btn { justify-content: center; width: 100%; }
}
</style>
