<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  report: { type: Object, default: null },
  cardPreview: { type: Object, default: null },
  reviewPlan: { type: Object, default: null },
  provider: { type: String, default: null },
  fallbackUsed: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  showReviewAction: { type: Boolean, default: false },
  reviewListAdded: { type: Boolean, default: false },
  reviewAdding: { type: Boolean, default: false }
})
const emit = defineEmits(['close', 'restart', 'add-review'])

const dimensions = computed(() => props.report?.dimensions || [])
const totalScore = computed(() => dimensions.value.reduce((sum, item) => sum + Number(item.score || 0), 0))
const averageScore = computed(() => dimensions.value.length ? (totalScore.value / dimensions.value.length).toFixed(1) : '—')
const weakest = computed(() => dimensions.value.length
  ? [...dimensions.value].sort((a, b) => Number(a.score) - Number(b.score))[0]
  : null)
const plan = computed(() => props.reviewPlan || props.report?.review_plan || null)
const rereadGuide = computed(() => [...(plan.value?.reread_guide || [])].sort((a, b) => a.priority - b.priority))
const relatedKps = computed(() => plan.value?.related_kps || [])
const hasDetailedEvidence = computed(() => dimensions.value.some(item =>
  item.evidence?.length || item.covered_points?.length || item.gaps?.length
))
const isLimited = computed(() => props.fallbackUsed || props.provider === 'mock')
const focusSummary = computed(() => props.cardPreview?.summary ||
  (weakest.value && Number(weakest.value.score) < 9
    ? `优先补强「${weakest.value.name}」`
    : '本轮未发现明显的低分维度'))

function level(score) {
  if (score >= 9) return '掌握扎实'
  if (score >= 7) return '主体正确'
  if (score >= 5) return '仍有缺口'
  return '需要重讲'
}

function closeOnEscape(event) {
  if (event.key === 'Escape' && props.open) emit('close')
}

let previousOverflow = ''
let lockedScroll = false
watch(() => props.open, (open) => {
  if (open && !lockedScroll) {
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', closeOnEscape)
    lockedScroll = true
  } else if (!open && lockedScroll) {
    document.body.style.overflow = previousOverflow
    window.removeEventListener('keydown', closeOnEscape)
    lockedScroll = false
  }
}, { immediate: true })

onBeforeUnmount(() => {
  if (lockedScroll) {
    document.body.style.overflow = previousOverflow
    window.removeEventListener('keydown', closeOnEscape)
  }
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="report-overlay" @click.self="$emit('close')">
      <section class="report-dialog" role="dialog" aria-modal="true" aria-label="费曼讲解诊断报告">
        <header class="report-header">
          <div>
            <span class="eyebrow">FEYNMAN · LEARNING DIAGNOSIS</span>
            <h2>{{ report?.kp_name || '本次讲解诊断' }}</h2>
            <p>依据本次用户讲解与当前知识点的评判基准生成</p>
          </div>
          <button class="close-button" type="button" aria-label="关闭报告" @click="$emit('close')">×</button>
        </header>

        <div v-if="loading" class="empty-state">正在读取完整诊断详情…</div>
        <div v-else-if="dimensions.length" class="report-content">
          <section class="overview" aria-label="综合表现">
            <div class="score-block">
              <span class="score-label">四维平均分</span>
              <div class="score-value">{{ averageScore }}<small>/ 10</small></div>
              <span class="score-footnote">四项合计 {{ totalScore }} / 40；分数用于定位下一步，不等于考试成绩</span>
            </div>
            <div class="overview-copy">
              <span class="section-kicker">本轮结论</span>
              <h3>{{ focusSummary }}</h3>
              <p>{{ report?.overall_comment || '请结合下面的逐维反馈继续完善讲解。' }}</p>
              <button
                v-if="showReviewAction"
                type="button"
                class="drawer-review-button"
                :class="{ 'drawer-review-button--added': reviewListAdded }"
                :disabled="reviewListAdded || reviewAdding"
                @click="$emit('add-review')"
              >
                {{ reviewListAdded ? '已加入待复习' : (reviewAdding ? '正在添加…' : '加入待复习') }}
              </button>
            </div>
          </section>

          <p v-if="isLimited" class="limited-note">这次使用了模拟或降级评估结果。页面仍展示完整流程，但分数和评语不能当作真实诊断；请确认模型配置与调用状态后重新讲解。</p>

          <section class="dimension-section" aria-label="四维诊断">
            <div class="section-heading">
              <div>
                <span class="section-kicker">01 / DIAGNOSIS</span>
                <h3>四维拆解</h3>
              </div>
              <span class="section-note">先看证据，再看分数与改进动作</span>
            </div>
            <p v-if="!hasDetailedEvidence" class="legacy-note">这份报告没有可核验的逐句证据（可能由旧版或降级流程生成）。以下只展示已有评语，不补造用户原话。</p>
            <article v-for="(dimension, index) in dimensions" :key="`${dimension.name}-${index}`" class="dimension-card">
              <div class="dimension-top">
                <span class="dimension-index">{{ String(index + 1).padStart(2, '0') }}</span>
                <div class="dimension-title">
                  <h4>{{ dimension.name }}</h4>
                  <span>{{ level(Number(dimension.score)) }}</span>
                </div>
                <strong>{{ dimension.score }}<small> / 10</small></strong>
              </div>
              <div class="score-track" role="progressbar" :aria-label="dimension.name" :aria-valuenow="dimension.score" aria-valuemin="0" aria-valuemax="10">
                <span :style="{ width: `${Math.max(0, Math.min(10, Number(dimension.score))) * 10}%` }"></span>
              </div>
              <div v-if="dimension.covered_points?.length || dimension.gaps?.length" class="findings">
                <div v-if="dimension.covered_points?.length" class="finding finding-good">
                  <span class="finding-label">你已讲到</span>
                  <ul><li v-for="(point, i) in dimension.covered_points" :key="i">{{ point }}</li></ul>
                </div>
                <div v-if="dimension.gaps?.length" class="finding finding-gap">
                  <span class="finding-label">待补强</span>
                  <ul><li v-for="(gap, i) in dimension.gaps" :key="i">{{ gap }}</li></ul>
                </div>
              </div>
              <div v-if="dimension.evidence?.length" class="evidence-list">
                <span class="finding-label">来自你的原话</span>
                <div v-for="(item, i) in dimension.evidence" :key="i" class="evidence-item">
                  <blockquote>“{{ item.quote }}”</blockquote>
                  <p>{{ item.observation }}</p>
                </div>
              </div>
              <p class="analysis"><span>判分依据</span>{{ dimension.analysis }}</p>
              <p class="next-action"><span>下一步</span>{{ dimension.suggestion }}</p>
            </article>
          </section>

          <section class="plan-section" aria-label="下一步复习建议">
            <div class="section-heading">
              <div>
                <span class="section-kicker">02 / NEXT STEP</span>
                <h3>接下来怎么练</h3>
              </div>
            </div>
            <div v-if="rereadGuide.length" class="plan-list">
              <article v-for="(item, index) in rereadGuide" :key="`${item.priority}-${index}`" class="plan-item">
                <span class="plan-rank">{{ String(index + 1).padStart(2, '0') }}</span>
                <div>
                  <div class="plan-meta">{{ report?.material_name || item.material_name || '当前教材' }}<span v-if="item.page_hint"> · {{ item.page_hint }}</span></div>
                  <h4>{{ item.focus }}</h4>
                  <p>{{ item.reason }}</p>
                </div>
              </article>
            </div>
            <p v-else class="plan-empty">本轮没有可靠的教材页码建议。先按上面最低分维度的“下一步”重新讲一遍，再对照教材核查。</p>
            <div v-if="relatedKps.length" class="related-list">
              <span>可关联学习</span>
              <p v-for="item in relatedKps" :key="item.kp_id">{{ item.kp_name }} · {{ item.relation }}</p>
            </div>
          </section>
        </div>
        <div v-else class="empty-state">报告详情正在加载，或当前记录缺少四维数据。</div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.report-overlay { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; padding: 24px; background: rgba(17, 30, 55, .58); }
.report-dialog { width: min(920px, 100%); max-height: min(88dvh, 920px); display: flex; flex-direction: column; overflow: hidden; background: #fff; border-radius: 18px; box-shadow: 0 28px 80px rgba(16, 32, 66, .24); }
.report-header { display: flex; justify-content: space-between; gap: 20px; padding: 25px 34px 20px; border-bottom: 1px solid #e9eef6; }
.eyebrow, .section-kicker { color: #3468d9; font-size: 10px; font-weight: 750; letter-spacing: .11em; }
.report-header h2 { margin: 6px 0 4px; color: #17233b; font-size: 23px; line-height: 1.35; }
.report-header p { margin: 0; color: #8b98ac; font-size: 12px; }
.close-button { width: 34px; height: 34px; flex: none; border: 1px solid #e4eaf3; border-radius: 9px; color: #67778f; background: #fff; font-size: 24px; line-height: 1; cursor: pointer; }
.close-button:hover { background: #f4f7fc; }
.report-content { min-height: 0; overflow-y: auto; padding: 25px 34px 36px; }
.overview { display: grid; grid-template-columns: 230px 1fr; gap: 22px; align-items: stretch; }
.score-block { display: flex; flex-direction: column; padding: 21px; border-radius: 14px; color: #fff; background: linear-gradient(145deg, #2361df, #3e69d4); }
.score-label { font-size: 12px; opacity: .86; }
.score-value { margin: 8px 0 6px; font-size: 43px; line-height: 1.1; font-weight: 750; letter-spacing: -.035em; }
.score-value small { font-size: 17px; font-weight: 500; opacity: .8; }
.score-footnote { margin-top: auto; font-size: 10px; line-height: 1.5; opacity: .78; }
.overview-copy { padding: 17px 20px; border: 1px solid #e8eef7; border-radius: 14px; background: #f9fbff; }
.overview-copy h3 { margin: 8px 0; color: #1b2b49; font-size: 18px; line-height: 1.4; }
.overview-copy p { margin: 0; color: #61718b; font-size: 13px; line-height: 1.75; white-space: pre-wrap; }
.drawer-review-button { margin-top: 14px; padding: 8px 12px; border-radius: 8px; background: #eaf1ff; color: #285fcf; font-size: 11px; font-weight: 650; }
.drawer-review-button--added { background: #edf8f3; color: #27815f; cursor: default; }
.dimension-section, .plan-section { margin-top: 31px; }
.section-heading { display: flex; justify-content: space-between; align-items: end; gap: 12px; margin-bottom: 15px; }
.section-heading h3 { margin: 4px 0 0; color: #1b2b49; font-size: 18px; }
.section-note { color: #91a0b4; font-size: 11px; }
.legacy-note { padding: 10px 12px; margin: 0 0 13px; border-radius: 9px; background: #f5f7fb; color: #77869b; font-size: 12px; line-height: 1.5; }
.limited-note { padding: 12px 14px; margin: 14px 0 0; border: 1px solid #f2d8ae; border-radius: 10px; background: #fff9ec; color: #9a6931; font-size: 12px; line-height: 1.6; }
.dimension-card { padding: 20px 22px; margin-bottom: 12px; border: 1px solid #e7edf6; border-radius: 14px; background: #fff; }
.dimension-top { display: flex; align-items: center; gap: 11px; }
.dimension-index { color: #9aaac2; font-size: 11px; font-weight: 750; }
.dimension-title { min-width: 0; flex: 1; display: flex; align-items: baseline; gap: 10px; }
.dimension-title h4 { margin: 0; color: #24354e; font-size: 15px; }
.dimension-title span { color: #8593a9; font-size: 11px; }
.dimension-top strong { color: #285fd3; font-size: 19px; }
.dimension-top strong small { color: #9aa7b9; font-size: 11px; font-weight: 500; }
.score-track { height: 5px; margin: 13px 0 16px; overflow: hidden; border-radius: 99px; background: #edf2fa; }
.score-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #78a4ff, #356be4); }
.findings { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.finding { padding: 12px 14px; border-radius: 10px; }
.finding-good { background: #f1f9f5; }
.finding-gap { background: #fff8ef; }
.finding-label { display: block; margin-bottom: 7px; color: #6e7e96; font-size: 11px; font-weight: 700; }
.finding-good .finding-label { color: #33815e; }
.finding-gap .finding-label { color: #a97331; }
.finding ul { margin: 0; padding-left: 17px; color: #34465e; font-size: 12px; line-height: 1.65; }
.finding li + li { margin-top: 4px; }
.evidence-list { padding: 12px 14px; margin-bottom: 14px; border-left: 3px solid #9db9f6; border-radius: 0 9px 9px 0; background: #f7faff; }
.evidence-item + .evidence-item { margin-top: 9px; padding-top: 9px; border-top: 1px solid #e5ecf8; }
.evidence-item blockquote { margin: 0 0 4px; color: #23395d; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }
.evidence-item p { margin: 0; color: #70819a; font-size: 11px; line-height: 1.6; }
.analysis, .next-action { display: flex; gap: 10px; margin: 8px 0 0; color: #576983; font-size: 12px; line-height: 1.65; }
.analysis span, .next-action span { flex: none; min-width: 48px; color: #8a98ad; font-weight: 650; }
.next-action { padding: 10px 12px; margin-top: 13px; border-radius: 9px; color: #2454b9; background: #f0f5ff; }
.next-action span { color: #4774c9; }
.plan-list { display: flex; flex-direction: column; gap: 9px; }
.plan-item { display: flex; align-items: flex-start; gap: 14px; padding: 16px 18px; border: 1px solid #e7edf6; border-radius: 11px; }
.plan-rank { color: #4777dc; font-size: 14px; font-weight: 750; }
.plan-meta { color: #8391a8; font-size: 11px; }
.plan-item h4 { margin: 5px 0; color: #253957; font-size: 13px; }
.plan-item p, .plan-empty { margin: 0; color: #687b96; font-size: 12px; line-height: 1.65; }
.plan-empty { padding: 15px; border-radius: 10px; background: #f6f8fc; }
.related-list { margin-top: 16px; color: #75849a; font-size: 12px; }
.related-list span { display: block; margin-bottom: 6px; font-weight: 700; }
.related-list p { margin: 4px 0; }
.empty-state { padding: 70px 20px; text-align: center; color: #8290a6; font-size: 13px; }
@media (max-width: 680px) {
  .report-overlay { padding: 0; align-items: end; }
  .report-dialog { max-height: 96dvh; border-radius: 16px 16px 0 0; }
  .report-header { padding: 20px; }
  .report-content { padding: 20px 16px 32px; }
  .overview, .findings { grid-template-columns: 1fr; }
  .score-block { min-height: 145px; }
  .section-note { display: none; }
  .dimension-card { padding: 16px; }
}
</style>
