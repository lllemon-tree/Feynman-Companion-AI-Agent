<script setup>
import { computed } from 'vue'

const props = defineProps({
  cardPreview: { type: Object, required: true },
  finalReport: { type: Object, default: null },
  provider: { type: String, default: null },
  fallbackUsed: { type: Boolean, default: false },
  reviewListAdded: { type: Boolean, default: false },
  reviewListSource: { type: String, default: null },
  reviewAdding: { type: Boolean, default: false },
  showReviewAction: { type: Boolean, default: true }
})
defineEmits(['click', 'add-review'])

const dimensions = computed(() => props.finalReport?.dimensions || [])
const totalScore = computed(() => dimensions.value.length
  ? dimensions.value.reduce((sum, item) => sum + Number(item.score || 0), 0)
  : Number(props.cardPreview?.total_score || 0))
const averageScore = computed(() => (totalScore.value / 4).toFixed(1))
const summary = computed(() => props.cardPreview?.summary || '查看完整的逐维反馈与复习建议')
const isLimited = computed(() => props.fallbackUsed || props.provider === 'mock')
</script>

<template>
  <article class="report-card" role="button" tabindex="0" @click="$emit('click')" @keydown.enter="$emit('click')">
    <span class="eyebrow"><span class="status-dot"></span> 本轮讲解完成 · {{ isLimited ? '降级诊断' : '诊断已生成' }}</span>
    <div class="report-main">
      <div class="score-box">
        <strong>{{ averageScore }}</strong><span>/ 10</span>
        <small>四维平均分</small>
      </div>
      <div class="report-copy">
        <span>优先关注</span>
        <h3>{{ summary }}</h3>
        <div v-if="dimensions.length" class="dimension-scores">
          <span v-for="item in dimensions" :key="item.name">{{ item.name }} <b>{{ item.score }}</b></span>
        </div>
      </div>
      <span class="report-arrow" aria-hidden="true">→</span>
    </div>
    <div class="report-footer">
      <span class="report-hint">{{ isLimited ? '本轮未使用正式模型评估，分数仅供流程演示，请勿当作真实掌握度。' : '打开报告，逐项查看讲对的内容、原话证据、待补强点与复习路径' }}</span>
      <button
        v-if="showReviewAction"
        type="button"
        class="review-button"
        :class="{ 'review-button--added': reviewListAdded }"
        :disabled="reviewListAdded || reviewAdding"
        @click.stop="$emit('add-review')"
      >
        {{ reviewListAdded ? (reviewListSource === 'automatic' ? '低于6分，已自动加入复习列表' : '已加入复习列表') : (reviewAdding ? '正在添加…' : '添加到复习列表') }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.report-card { display: block; width: calc(100% - 43px); margin-left: 43px; padding: 19px 21px; border: 1px solid #dce7f8; border-radius: 15px; background: linear-gradient(125deg, #f7faff, #fff 58%); color: #1d2d49; text-align: left; box-shadow: 0 7px 25px rgba(31, 77, 161, .06); cursor: pointer; transition: border-color .15s, transform .15s, box-shadow .15s; }
.report-card:hover { border-color: #a9c3f2; transform: translateY(-1px); box-shadow: 0 10px 28px rgba(31, 77, 161, .1); }
.report-card:focus-visible { outline: 3px solid #a6c2fb; outline-offset: 3px; }
.eyebrow { display: inline-flex; align-items: center; gap: 7px; color: #3c67c4; font-size: 11px; font-weight: 750; letter-spacing: .03em; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #2dcb8c; }
.report-main { display: flex; align-items: center; gap: 21px; margin: 16px 0 12px; }
.score-box { flex: none; min-width: 115px; padding-right: 20px; border-right: 1px solid #dfe7f2; }
.score-box strong { color: #235bd1; font-size: 34px; line-height: 1; letter-spacing: -.035em; }
.score-box span { margin-left: 4px; color: #8b9aaf; font-size: 14px; }
.score-box small { display: block; margin-top: 4px; color: #8b9aaf; font-size: 10px; white-space: nowrap; }
.report-copy { min-width: 0; flex: 1; }
.report-copy > span { color: #8594aa; font-size: 11px; }
.report-copy h3 { margin: 4px 0 8px; color: #263955; font-size: 15px; line-height: 1.4; }
.dimension-scores { display: flex; flex-wrap: wrap; gap: 7px 12px; color: #7486a0; font-size: 11px; }
.dimension-scores b { color: #3265d5; font-weight: 750; }
.report-arrow { display: grid; place-items: center; flex: none; width: 27px; height: 27px; border-radius: 50%; background: #e7efff; color: #3264d6; font-size: 19px; }
.report-footer { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding-top: 10px; border-top: 1px solid #e6edf7; }
.report-hint { display: block; min-width: 0; color: #8b9aaf; font-size: 11px; }
.review-button { flex: none; padding: 7px 11px; border-radius: 8px; background: #eaf1ff; color: #285fcf; font-size: 11px; font-weight: 650; cursor: pointer; }
.review-button:hover:not(:disabled) { background: #dce8ff; }
.review-button--added { background: #edf8f3; color: #27815f; cursor: default; }
@media (max-width: 680px) {
  .report-card { width: 100%; margin-left: 0; padding: 16px; }
  .report-main { gap: 13px; }
  .score-box { min-width: 85px; padding-right: 12px; }
  .score-box strong { font-size: 28px; }
  .score-box small { display: none; }
  .report-arrow { display: none; }
  .report-footer { align-items: flex-start; flex-direction: column; }
  .review-button { width: 100%; }
}
</style>
