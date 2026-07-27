<script setup>
import { ref, onBeforeUnmount, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getKnowledgeTree, getKpDetail, createKp, updateKp, deleteKp, regenerateKp } from '@/api/feynman'

const router = useRouter()
const route = useRoute()

const materialId = computed(() => route.query.materialId)
const materialName = computed(() => decodeURIComponent(route.query.name || '教材知识点'))
const subject = computed(() => route.query.subject || '计算机')

const chapters = ref([])
const loading = ref(false)
const kpPollingTimers = new Map()

const modal = ref(null)
const chunkPreview = ref(null)
const chunkPreviewLoading = ref(false)
const chunkPreviewError = ref('')
const formValues = ref({ name: '', pageStart: '', pageEnd: '' })
const formErrors = ref({})

const STATUS_CONFIG = {
  done: { label: '已完成', color: 'text-green-600', icon: 'check' },
  pending_regenerate: { label: 'rubric生成中', color: 'text-amber-600', icon: 'clock' },
  failed: { label: '生成失败', color: 'text-red-500', icon: 'alert' },
}

async function loadKnowledgeTree() {
  loading.value = true
  try {
    const tree = await getKnowledgeTree(subject.value)
    const material = tree.find(m => m.material_id === materialId.value)
    if (material) {
      chapters.value = material.chapters.map(ch => ({
        id: ch.chapter_id,
        title: ch.title,
        expanded: true,
        kps: ch.knowledge_points.map(kp => ({
          id: kp.kp_id,
          name: kp.name,
          pageStart: kp.page_start || 0,
          pageEnd: kp.page_end || 0,
          status: kp.status || 'pending_regenerate',
          summary: kp.summary
        }))
      }))
    } else {
      chapters.value = []
    }
  } catch (e) {
    console.error('加载知识点失败:', e)
    chapters.value = []
  } finally {
    loading.value = false
  }
}

function updateLocalKp(chapterId, kpId, patch) {
  chapters.value = chapters.value.map(ch =>
    ch.id !== chapterId
      ? ch
      : {
          ...ch,
          kps: ch.kps.map(kp => kp.id === kpId ? { ...kp, ...patch } : kp)
        }
  )
}

function stopKpPolling(kpId) {
  const timer = kpPollingTimers.get(kpId)
  if (timer) clearTimeout(timer)
  kpPollingTimers.delete(kpId)
}

async function pollKpUntilSettled(chapterId, kpId) {
  stopKpPolling(kpId)

  const poll = async () => {
    try {
      const detail = await getKpDetail(kpId)
      updateLocalKp(chapterId, kpId, {
        name: detail.name,
        summary: detail.summary,
        pageStart: detail.page_start,
        pageEnd: detail.page_end,
        status: detail.status
      })
      if (detail.status === 'done' || detail.status === 'failed') {
        stopKpPolling(kpId)
        return
      }
      kpPollingTimers.set(kpId, setTimeout(poll, 2000))
    } catch (e) {
      stopKpPolling(kpId)
      console.error('轮询知识点状态失败:', e)
    }
  }

  await poll()
}

function toggleChapter(id) {
  chapters.value = chapters.value.map(ch => 
    ch.id === id ? { ...ch, expanded: !ch.expanded } : ch
  )
}

function openAddModal(chapterId) {
  modal.value = { type: 'add', chapterId }
  formValues.value = { name: '', pageStart: '', pageEnd: '' }
  formErrors.value = {}
}

function openEditModal(chapterId, kp) {
  modal.value = { type: 'edit', chapterId, kpId: kp.id, prevKp: kp }
  formValues.value = {
    name: kp.name,
    pageStart: kp.pageStart.toString(),
    pageEnd: kp.pageEnd.toString()
  }
  formErrors.value = {}
}

function openDeleteModal(chapterId, kp) {
  modal.value = { type: 'delete', chapterId, kp }
}

async function openChunkPreview(kp) {
  chunkPreview.value = { kpName: kp.name, chunks: [] }
  chunkPreviewLoading.value = true
  chunkPreviewError.value = ''
  try {
    const detail = await getKpDetail(kp.id)
    chunkPreview.value = {
      kpName: detail.name,
      chunks: detail.source_chunks || []
    }
  } catch (e) {
    chunkPreviewError.value = e.message || '原文切片加载失败'
  } finally {
    chunkPreviewLoading.value = false
  }
}

function validateForm() {
  const errs = {}
  if (!formValues.value.name.trim()) errs.name = '请填写知识点名称'
  const ps = parseInt(formValues.value.pageStart)
  const pe = parseInt(formValues.value.pageEnd)
  if (!formValues.value.pageStart || isNaN(ps) || ps < 1) errs.pageStart = '请输入正整数'
  if (!formValues.value.pageEnd || isNaN(pe) || pe < 1) errs.pageEnd = '请输入正整数'
  else if (!errs.pageStart && pe < ps) errs.pageEnd = '结束页码须≥起始页码'
  formErrors.value = errs
  return Object.keys(errs).length === 0
}

async function handleSubmit() {
  if (!validateForm()) return
  
  if (modal.value.type === 'add') {
    try {
      const result = await createKp(
        modal.value.chapterId,
        formValues.value.name.trim(),
        parseInt(formValues.value.pageStart),
        parseInt(formValues.value.pageEnd)
      )
      
      const newKp = {
        id: result.kp_id,
        name: formValues.value.name.trim(),
        pageStart: parseInt(formValues.value.pageStart),
        pageEnd: parseInt(formValues.value.pageEnd),
        status: result.status || 'pending_regenerate',
        summary: ''
      }
      chapters.value = chapters.value.map(ch => 
        ch.id === modal.value.chapterId 
          ? { ...ch, kps: [...ch.kps, newKp] } 
          : ch
      )
      
      pollKpUntilSettled(modal.value.chapterId, newKp.id)
    } catch (e) {
      console.error('创建知识点失败:', e)
    }
  } else if (modal.value.type === 'edit') {
    const pageChanged = 
      parseInt(formValues.value.pageStart) !== modal.value.prevKp.pageStart ||
      parseInt(formValues.value.pageEnd) !== modal.value.prevKp.pageEnd

    try {
      const updates = {
        name: formValues.value.name.trim(),
        page_start: parseInt(formValues.value.pageStart),
        page_end: parseInt(formValues.value.pageEnd)
      }
      await updateKp(modal.value.kpId, updates)

      chapters.value = chapters.value.map(ch => 
        ch.id !== modal.value.chapterId 
          ? ch 
          : {
              ...ch,
              kps: ch.kps.map(k => 
                k.id !== modal.value.kpId 
                  ? k 
                  : {
                      ...k,
                      name: formValues.value.name.trim(),
                      pageStart: parseInt(formValues.value.pageStart),
                      pageEnd: parseInt(formValues.value.pageEnd),
                      status: pageChanged ? 'pending_regenerate' : k.status,
                    }
              ),
            }
      )

      if (pageChanged) {
        pollKpUntilSettled(modal.value.chapterId, modal.value.kpId)
      }
    } catch (e) {
      console.error('更新知识点失败:', e)
    }
  }
  
  modal.value = null
}

async function handleDeleteConfirm() {
  try {
    await deleteKp(modal.value.kp.id)
    chapters.value = chapters.value.map(ch => 
      ch.id !== modal.value.chapterId 
        ? ch 
        : { ...ch, kps: ch.kps.filter(k => k.id !== modal.value.kp.id) }
    )
  } catch (e) {
    console.error('删除知识点失败:', e)
  }
  modal.value = null
}

async function handleRegenerate(chapterId, kpId) {
  try {
    await regenerateKp(kpId)
    chapters.value = chapters.value.map(ch => 
      ch.id !== chapterId 
        ? ch 
        : {
            ...ch,
            kps: ch.kps.map(k => 
              k.id === kpId ? { ...k, status: 'pending_regenerate' } : k
            ),
          }
    )
    
    pollKpUntilSettled(chapterId, kpId)
  } catch (e) {
    console.error('重新生成失败:', e)
  }
}

function goBack() {
  router.push('/upload')
}

function goToSelect() {
  router.push(`/select`)
}

onMounted(() => {
  loadKnowledgeTree()
})

onBeforeUnmount(() => {
  kpPollingTimers.forEach(timer => clearTimeout(timer))
  kpPollingTimers.clear()
})
</script>

<template>
  <div class="knowledge-page">
    <header class="knowledge-header">
      <button class="back-btn" @click="goBack">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        返回
      </button>
      <div class="header-title">
        <h1 class="page-title">{{ materialName }}</h1>
      </div>
      <div class="header-actions">
        <button class="select-btn" @click="goToSelect">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
          开始学习
        </button>
        <button class="add-btn" @click="chapters.length > 0 && openAddModal(chapters[0].id)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          新增知识点
        </button>
      </div>
    </header>

    <main class="knowledge-main">
      <div v-if="loading" class="loading-state">
        <div class="spinner">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
          </svg>
        </div>
        <p>加载中...</p>
      </div>

      <div v-else-if="chapters.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </div>
        <p>暂无知识点</p>
      </div>

      <div v-else>
        <div v-for="chapter in chapters" :key="chapter.id" class="chapter-group">
          <button class="chapter-header" @click="toggleChapter(chapter.id)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'rotate-90': !chapter.expanded }">
              <polyline points="6 9 12 15 18 9" />
            </svg>
            <span class="chapter-title">{{ chapter.title }}</span>
            <span class="chapter-count">({{ chapter.kps.length }})</span>
            <button class="add-kp-link" @click.stop="openAddModal(chapter.id)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              添加
            </button>
          </button>

          <div v-if="chapter.expanded" class="kp-list">
            <div v-if="chapter.kps.length === 0" class="empty-kp">
              暂无知识点，点击上方添加
            </div>
            <div v-else>
              <div
                v-for="kp in chapter.kps"
                :key="kp.id"
                class="kp-row"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="kp-icon">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>

                <div class="kp-info">
                  <span class="kp-name">{{ kp.name }}</span>
                  <span class="kp-page">p.{{ kp.pageStart }}–{{ kp.pageEnd }}</span>
                </div>

                <div class="kp-status" :class="STATUS_CONFIG[kp.status].color">
                  <svg v-if="STATUS_CONFIG[kp.status].icon === 'check'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <svg v-else-if="STATUS_CONFIG[kp.status].icon === 'clock'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{{ STATUS_CONFIG[kp.status].label }}</span>
                </div>

                <div class="kp-actions">
                  <button
                    v-if="kp.status === 'done'"
                    class="action-btn"
                    title="查看原文切片"
                    aria-label="查看原文切片"
                    @click="openChunkPreview(kp)"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M4 4h16v16H4z" />
                      <path d="M8 8h8M8 12h8M8 16h5" />
                    </svg>
                  </button>
                  <button
                    v-if="kp.status === 'done' || kp.status === 'failed'"
                    class="action-btn"
                    title="重新生成rubric"
                    @click="handleRegenerate(chapter.id, kp.id)"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                      <path d="M3 3v5h5" />
                      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
                      <path d="M16 21h5v-5" />
                    </svg>
                  </button>
                  <button class="action-btn" title="编辑" @click="openEditModal(chapter.id, kp)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                    </svg>
                  </button>
                  <button class="action-btn action-btn--delete" title="删除" @click="openDeleteModal(chapter.id, kp)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <div v-if="modal" class="modal-overlay" @click="modal = null">
      <div class="kp-modal" @click.stop>
        <template v-if="modal.type === 'add' || modal.type === 'edit'">
          <div class="modal-header">
            <h2>{{ modal.type === 'add' ? '新增知识点' : '编辑知识点' }}</h2>
            <button class="close-btn" @click="modal = null">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <div class="form-group">
              <label>知识点名称 <span class="required">*</span></label>
              <input
                v-model="formValues.name"
                type="text"
                placeholder="例：Dijkstra算法"
                class="form-input"
                :class="{ 'form-input--error': formErrors.name }"
              />
              <span v-if="formErrors.name" class="error-text">{{ formErrors.name }}</span>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>起始页码</label>
                <input
                  v-model="formValues.pageStart"
                  type="number"
                  min="1"
                  placeholder="如 45"
                  class="form-input"
                  :class="{ 'form-input--error': formErrors.pageStart }"
                />
                <span v-if="formErrors.pageStart" class="error-text">{{ formErrors.pageStart }}</span>
              </div>
              <div class="form-group">
                <label>结束页码</label>
                <input
                  v-model="formValues.pageEnd"
                  type="number"
                  min="1"
                  placeholder="如 52"
                  class="form-input"
                  :class="{ 'form-input--error': formErrors.pageEnd }"
                />
                <span v-if="formErrors.pageEnd" class="error-text">{{ formErrors.pageEnd }}</span>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-cancel" @click="modal = null">取消</button>
            <button class="btn-confirm" @click="handleSubmit">确定</button>
          </div>
        </template>

        <template v-else-if="modal.type === 'delete'">
          <div class="modal-header">
            <h2>确认删除</h2>
            <button class="close-btn" @click="modal = null">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <div class="delete-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </div>
            <p>即将删除知识点「<strong>{{ modal.kp.name }}</strong>」，此操作不可撤销。</p>
          </div>

          <div class="modal-footer">
            <button class="btn-cancel" @click="modal = null">取消</button>
            <button class="btn-delete" @click="handleDeleteConfirm">确认删除</button>
          </div>
        </template>
      </div>
    </div>

    <div v-if="chunkPreview" class="modal-overlay" @click="chunkPreview = null">
      <div class="kp-modal chunk-modal" @click.stop>
        <div class="modal-header">
          <div>
            <h2>教材原文切片</h2>
            <div class="chunk-modal-subtitle">{{ chunkPreview.kpName }}</div>
          </div>
          <button class="close-btn" @click="chunkPreview = null">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div class="chunk-modal-body">
          <div v-if="chunkPreviewLoading" class="chunk-empty">正在读取切片...</div>
          <div v-else-if="chunkPreviewError" class="chunk-error">{{ chunkPreviewError }}</div>
          <div v-else-if="chunkPreview.chunks.length === 0" class="chunk-empty">该知识点页码范围内没有原文切片</div>
          <article v-for="chunk in chunkPreview.chunks" v-else :key="chunk.chunk_id" class="chunk-item">
            <div class="chunk-meta">
              <span>第 {{ chunk.page }} 页</span>
              <code>{{ chunk.chunk_id }}</code>
            </div>
            <p>{{ chunk.text }}</p>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-page {
  min-height: 100vh;
  background: #F8FAFC;
  display: flex;
  flex-direction: column;
  font-family: 'Noto Sans SC', 'Inter', sans-serif;
}

.knowledge-header {
  position: sticky;
  top: 0;
  z-index: 30;
  background: #FFFFFF;
  border-bottom: 1px solid #E2E8F0;
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #64748B;
  transition: color 150ms;
}

.back-btn:hover {
  color: #1E293B;
}

.header-title {
  flex: 1;
  min-width: 0;
}

.page-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: #2563EB;
  color: #FFFFFF;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  transition: all 150ms;
}

.add-btn:hover {
  background: #1D4ED8;
}

.add-btn:active {
  transform: scale(0.98);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.select-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: #F1F5F9;
  color: #475569;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  transition: all 150ms;
}

.select-btn:hover {
  background: #E2E8F0;
  color: #334155;
}

.knowledge-main {
  flex: 1;
  padding: 28px 16px;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  gap: 12px;
}

.loading-state .spinner {
  animation: spin 1s linear infinite;
  color: #2563EB;
}

.loading-state p {
  margin: 0;
  font-size: 14px;
  color: #94A3B8;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px;
  gap: 8px;
}

.empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: #F1F5F9;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94A3B8;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
  color: #94A3B8;
}

.chapter-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chapter-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
  transition: all 150ms;
}

.chapter-header:hover .chapter-title {
  color: #2563EB;
}

.chapter-title {
  flex: 1;
  transition: color 150ms;
}

.chapter-count {
  font-size: 13px;
  color: #94A3B8;
  font-weight: 400;
}

.add-kp-link {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #2563EB;
  font-weight: 500;
  opacity: 0;
  transition: opacity 150ms;
}

.chapter-header:hover .add-kp-link {
  opacity: 1;
}

.kp-list {
  margin-left: 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.empty-kp {
  padding: 24px;
  text-align: center;
  font-size: 14px;
  color: #94A3B8;
}

.kp-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  transition: all 150ms;
}

.kp-row:hover {
  background: #F8FAFC;
}

.kp-icon {
  color: #94A3B8;
}

.kp-info {
  flex: 1;
  min-width: 0;
}

.kp-name {
  font-size: 14px;
  font-weight: 500;
  color: #1E293B;
}

.kp-page {
  font-size: 13px;
  color: #94A3B8;
  margin-left: 8px;
}

.kp-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
}

.kp-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94A3B8;
  transition: all 150ms;
}

.action-btn:hover {
  background: #F1F5F9;
  color: #1E293B;
}

.action-btn--delete:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 15, 30, 0.65);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.kp-modal {
  background: #FFFFFF;
  border-radius: 16px;
  width: 90%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.chunk-modal {
  max-width: 720px;
  max-height: min(80vh, 760px);
}

.chunk-modal-subtitle {
  margin-top: 3px;
  color: #64748B;
  font-size: 12px;
}

.chunk-modal-body {
  padding: 16px 20px 20px;
  overflow-y: auto;
}

.chunk-item {
  padding: 14px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  background: #F8FAFC;
}

.chunk-item + .chunk-item {
  margin-top: 10px;
}

.chunk-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #2563EB;
  font-size: 12px;
  font-weight: 600;
}

.chunk-meta code {
  overflow: hidden;
  color: #64748B;
  font-size: 11px;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chunk-item p {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.chunk-empty,
.chunk-error {
  padding: 28px 12px;
  color: #64748B;
  font-size: 13px;
  text-align: center;
}

.chunk-error {
  color: #DC2626;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid #E2E8F0;
}

.modal-header h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748B;
  transition: all 150ms;
}

.close-btn:hover {
  background: #F1F5F9;
  color: #1E293B;
}

.modal-body {
  padding: 20px 24px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #1E293B;
  margin-bottom: 6px;
}

.required {
  color: #EF4444;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  font-size: 14px;
  transition: all 150ms;
}

.form-input:focus {
  border-color: rgba(37, 99, 235, 0.3);
  outline: none;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

.form-input--error {
  border-color: #F87171;
  background: rgba(248, 113, 113, 0.05);
}

.error-text {
  display: block;
  font-size: 12px;
  color: #EF4444;
  margin-top: 4px;
}

.form-row {
  display: flex;
  gap: 12px;
}

.form-row .form-group {
  flex: 1;
}

.delete-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #EF4444;
  margin-bottom: 8px;
}

.modal-body p {
  margin: 0;
  font-size: 14px;
  color: #64748B;
  line-height: 1.6;
}

.modal-body strong {
  color: #1E293B;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #E2E8F0;
}

.btn-cancel {
  padding: 8px 16px;
  font-size: 14px;
  color: #64748B;
  border-radius: 10px;
  transition: all 150ms;
}

.btn-cancel:hover {
  background: #F1F5F9;
}

.btn-confirm {
  padding: 8px 20px;
  background: #2563EB;
  color: #FFFFFF;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  transition: all 150ms;
}

.btn-confirm:hover {
  background: #1D4ED8;
}

.btn-delete {
  padding: 8px 20px;
  background: #EF4444;
  color: #FFFFFF;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  transition: all 150ms;
}

.btn-delete:hover {
  background: #DC2626;
}

.rotate-90 {
  transform: rotate(-90deg);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
