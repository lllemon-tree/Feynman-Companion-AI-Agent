<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chatStore'
import { getKnowledgeTree, fetchGreeting, fetchSubjects } from '@/api/feynman'

const router = useRouter()
const chatStore = useChatStore()

const DEFAULT_SUBJECTS = [
  { value: '计算机', label: '计算机' },
  { value: '数学', label: '数学' },
  { value: '政治', label: '政治' }
]
const subjects = ref(DEFAULT_SUBJECTS)
const selectedSubject = ref('计算机')
const knowledgeTree = ref([])
const selectedMaterialId = ref('')
const selectedChapterId = ref('')
const selectedKpId = ref('')
const greetingText = ref('')
const loading = ref(false)

const dropdownOpen = ref({})

const materials = computed(() => (knowledgeTree.value || []).filter(m => m.status === 'done'))
const chapters = computed(() => {
  const material = materials.value.find(m => m.material_id === selectedMaterialId.value)
  return material?.chapters || []
})
const knowledgePoints = computed(() => {
  const chapter = chapters.value.find(c => c.chapter_id === selectedChapterId.value)
  return chapter?.knowledge_points || []
})
const selectedKp = computed(() => {
  return knowledgePoints.value.find(kp => kp.kp_id === selectedKpId.value)
})

const canStart = computed(() => !!selectedKpId.value)
const showChapters = computed(() => !!selectedMaterialId.value)
const showKps = computed(() => !!selectedChapterId.value)

const materialOptions = computed(() => {
  if (materials.value.length === 0) {
    return [{ value: '', label: '暂无教材', disabled: true }]
  }
  return materials.value.map(m => ({ value: m.material_id, label: m.title }))
})

const chapterOptions = computed(() => {
  if (!selectedMaterialId.value) return []
  if (chapters.value.length === 0) {
    return [{ value: '', label: '暂无章节', disabled: true }]
  }
  return chapters.value.map(c => ({ value: c.chapter_id, label: c.title }))
})

async function loadKnowledgeTree() {
  loading.value = true
  try {
    const data = await getKnowledgeTree(selectedSubject.value)
    knowledgeTree.value = data
    if (data.length > 0) {
      selectedMaterialId.value = data[0].material_id
      const firstCh = data[0].chapters[0]
      if (firstCh) {
        selectedChapterId.value = firstCh.chapter_id
        const firstKp = firstCh.knowledge_points[0]
        if (firstKp) {
          selectedKpId.value = firstKp.kp_id
          loadGreeting(firstKp.kp_id)
        } else {
          selectedKpId.value = ''
        }
      } else {
        selectedChapterId.value = ''
        selectedKpId.value = ''
      }
    } else {
      selectedMaterialId.value = ''
      selectedChapterId.value = ''
      selectedKpId.value = ''
    }
  } catch (e) {
    showToastMsg('加载数据失败，请重新切换选项')
  } finally {
    loading.value = false
  }
}

async function loadGreeting(kpId) {
  try {
    const greeting = await fetchGreeting(kpId)
    greetingText.value = greeting.reply_text
  } catch (e) {
    console.warn('预加载 greeting 失败:', e)
  }
}

function handleSubjectChange(v) {
  selectedSubject.value = v
  selectedMaterialId.value = ''
  selectedChapterId.value = ''
  selectedKpId.value = ''
  greetingText.value = ''
  loadKnowledgeTree()
}

function handleMaterialChange(v) {
  selectedMaterialId.value = v
  selectedChapterId.value = ''
  selectedKpId.value = ''
  greetingText.value = ''
  const mat = materials.value.find(m => m.material_id === v)
  const firstCh = mat?.chapters[0]
  if (firstCh) {
    selectedChapterId.value = firstCh.chapter_id
    const firstKp = firstCh.knowledge_points[0]
    if (firstKp) {
      selectedKpId.value = firstKp.kp_id
      loadGreeting(firstKp.kp_id)
    }
  }
}

function handleChapterChange(v) {
  selectedChapterId.value = v
  selectedKpId.value = ''
  greetingText.value = ''
  const ch = chapters.value.find(c => c.chapter_id === v)
  const firstKp = ch?.knowledge_points[0]
  if (firstKp) {
    selectedKpId.value = firstKp.kp_id
    loadGreeting(firstKp.kp_id)
  }
}

function handleKpSelect(kpId) {
  selectedKpId.value = kpId
  loadGreeting(kpId)
}

async function startFeynman() {
  if (!selectedKp.value) return
  const kp = selectedKp.value
  const material = materials.value.find(m => m.material_id === selectedMaterialId.value)
  const chapter = chapters.value.find(c => c.chapter_id === selectedChapterId.value)
  const subjectLabel = subjects.find(s => s.value === selectedSubject.value)?.label || ''

  chatStore.setSubject(subjectLabel)
  chatStore.setMaterial(selectedMaterialId.value, material?.title || '')
  chatStore.setChapter(selectedChapterId.value, chapter?.title || '')
  chatStore.setKnowledgePoint(kp.kp_id, kp.name)
  router.push('/home')
}

function showToastMsg(msg) {
  toastMessage.value = msg
  showToast.value = true
  setTimeout(() => {
    showToast.value = false
  }, 3000)
}

function goToUploadPage() {
  router.push('/upload')
}

function toggleDropdown(key) {
  dropdownOpen.value[key] = !dropdownOpen.value[key]
}

function closeDropdown(key) {
  dropdownOpen.value[key] = false
}

const toastMessage = ref('')
const showToast = ref(false)

onMounted(async () => {
  try {
    const storedSubjects = await fetchSubjects()
    const values = [...new Set([...DEFAULT_SUBJECTS.map(item => item.value), ...storedSubjects])]
    subjects.value = values.map(value => ({ value, label: value }))
  } catch (e) {
    console.warn('加载科目列表失败，使用默认科目:', e)
  }
  loadKnowledgeTree()
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown-wrapper')) {
      Object.keys(dropdownOpen.value).forEach(key => {
        dropdownOpen.value[key] = false
      })
    }
  })
})
</script>

<template>
  <div class="select-page">
    <header class="select-header">
      <h1 class="page-title">选择知识点开始费曼学习</h1>
      <button class="upload-entry-btn" @click="goToUploadPage">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        上传教材
      </button>
    </header>

    <main class="select-main">
      <div class="cascade-container">
        <div class="cascade-row">
          <div class="cascade-step">
            <div class="step-circle">1</div>
            <div class="step-line"></div>
          </div>
          <div class="cascade-content">
            <div class="cascade-label">科目</div>
            <div class="dropdown-wrapper">
              <button class="dropdown-btn" @click="toggleDropdown('subject')">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <rect x="3" y="3" width="7" height="7" rx="1" />
                  <rect x="14" y="3" width="7" height="7" rx="1" />
                  <rect x="3" y="14" width="7" height="7" rx="1" />
                  <rect x="14" y="14" width="7" height="7" rx="1" />
                </svg>
                <span>{{ subjects.find(s => s.value === selectedSubject)?.label }}</span>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'rotate-180': dropdownOpen['subject'] }">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              <div v-if="dropdownOpen['subject']" class="dropdown-menu">
                <button
                  v-for="s in subjects"
                  :key="s.value"
                  class="dropdown-item"
                  :class="{ 'dropdown-item--selected': s.value === selectedSubject }"
                  @click="handleSubjectChange(s.value); closeDropdown('subject')"
                >
                  {{ s.label }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="cascade-row">
          <div class="cascade-step">
            <div class="step-circle">2</div>
            <div class="step-line"></div>
          </div>
          <div class="cascade-content">
            <div class="cascade-label">教材</div>
            <div class="dropdown-wrapper">
              <button
                class="dropdown-btn"
                :disabled="materials.length === 0 || loading"
                @click="toggleDropdown('material')"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
                <span>{{ materialOptions.find(o => o.value === selectedMaterialId)?.label || '请选择教材' }}</span>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'rotate-180': dropdownOpen['material'] }">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              <div v-if="dropdownOpen['material']" class="dropdown-menu">
                <button
                  v-for="opt in materialOptions"
                  :key="opt.value"
                  class="dropdown-item"
                  :class="{ 'dropdown-item--selected': opt.value === selectedMaterialId, 'dropdown-item--disabled': opt.disabled }"
                  :disabled="opt.disabled"
                  @click="!opt.disabled && (handleMaterialChange(opt.value), closeDropdown('material'))"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="cascade-row">
          <div class="cascade-step">
            <div class="step-circle">3</div>
            <div class="step-line"></div>
          </div>
          <div class="cascade-content">
            <div class="cascade-label">章节</div>
            <div v-if="showChapters" class="dropdown-wrapper">
              <button
                class="dropdown-btn"
                :disabled="chapterOptions.length === 0 || (chapterOptions[0]?.disabled ?? false)"
                @click="toggleDropdown('chapter')"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
                <span>{{ chapterOptions.find(o => o.value === selectedChapterId)?.label || '请选择章节' }}</span>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'rotate-180': dropdownOpen['chapter'] }">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              <div v-if="dropdownOpen['chapter']" class="dropdown-menu">
                <button
                  v-for="opt in chapterOptions"
                  :key="opt.value"
                  class="dropdown-item"
                  :class="{ 'dropdown-item--selected': opt.value === selectedChapterId, 'dropdown-item--disabled': opt.disabled }"
                  :disabled="opt.disabled"
                  @click="!opt.disabled && (handleChapterChange(opt.value), closeDropdown('chapter'))"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>
            <div v-else class="placeholder-box">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
              </svg>
              请先选择教材
            </div>
          </div>
        </div>

        <div class="cascade-row">
          <div class="cascade-step">
            <div class="step-circle">4</div>
          </div>
          <div class="cascade-content">
            <div class="cascade-label">知识点</div>
            <div v-if="!showKps" class="placeholder-box">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
              请先选择章节
            </div>
            <div v-else-if="knowledgePoints.length === 0" class="empty-kp-box">
              当前章节暂无知识点，请前往
              <button class="link-btn" @click="goToUploadPage">教材管理</button>
              页面新增
            </div>
            <div v-else class="kp-list">
              <button
                v-for="kp in knowledgePoints"
                :key="kp.kp_id"
                class="kp-card"
                :class="{ 'kp-card--selected': selectedKpId === kp.kp_id }"
                @click="handleKpSelect(kp.kp_id)"
              >
                <div class="kp-radio" :class="{ 'kp-radio--selected': selectedKpId === kp.kp_id }">
                  <div v-if="selectedKpId === kp.kp_id" class="radio-inner"></div>
                </div>
                <div class="kp-content">
                  <div class="kp-name">
                    {{ kp.name }}
                  </div>
                  <div v-if="kp.summary" class="kp-summary">{{ kp.summary }}</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="greetingText && selectedKp" class="greeting-preview">
        <div class="greeting-avatar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="5" y="8" width="14" height="10" rx="2" fill="#2563EB" />
            <rect x="9" y="11" width="2" height="2" rx="0.5" fill="#fff" />
            <rect x="13" y="11" width="2" height="2" rx="0.5" fill="#fff" />
            <rect x="10.5" y="5" width="3" height="3" rx="1" fill="#2563EB" />
            <circle cx="12" cy="4.5" r="1" fill="#60A5FA" />
          </svg>
        </div>
        <div class="greeting-content">
          <div class="greeting-label">引导语预览</div>
          <p class="greeting-text">{{ greetingText }}</p>
        </div>
      </div>
    </main>

    <footer class="select-footer">
      <div class="footer-inner">
        <button
          class="start-btn"
          :disabled="!canStart"
          @click="startFeynman"
        >
          <span>开始费曼讲解</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
        <p v-if="!canStart" class="footer-hint">请先选择一个知识点</p>
      </div>
    </footer>

    <div v-if="showToast" class="toast">{{ toastMessage }}</div>
  </div>
</template>

<style scoped>
.select-page {
  min-height: 100vh;
  background: #F8FAFC;
  display: flex;
  flex-direction: column;
  font-family: 'Noto Sans SC', 'Inter', sans-serif;
}

.select-header {
  position: sticky;
  top: 0;
  z-index: 30;
  background: #FFFFFF;
  border-bottom: 1px solid #E2E8F0;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.page-title {
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
}

.upload-entry-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  background: #FFFFFF;
  color: #1E293B;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 150ms, border-color 150ms, color 150ms;
}

.upload-entry-btn:hover {
  border-color: #2563EB;
  background: #EFF6FF;
  color: #1D4ED8;
}

.select-main {
  flex: 1;
  padding: 32px 16px;
  max-width: 480px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.cascade-container {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.cascade-row {
  display: flex;
  gap: 16px;
}

.cascade-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 32px;
  padding-top: 12px;
}

.step-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #2563EB;
  color: #FFFFFF;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.2);
}

.step-line {
  flex: 1;
  width: 2px;
  background: #E2E8F0;
  margin: 4px 0;
  min-height: 24px;
}

.cascade-content {
  flex: 1;
  min-width: 0;
  padding-bottom: 20px;
}

.cascade-label {
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
  margin-bottom: 8px;
  padding-top: 6px;
}

.dropdown-wrapper {
  position: relative;
}

.dropdown-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  font-size: 14px;
  color: #1E293B;
  background: #FFFFFF;
  transition: all 150ms;
}

.dropdown-btn:hover:not(:disabled) {
  border-color: rgba(37, 99, 235, 0.5);
}

.dropdown-btn:focus-visible {
  outline: none;
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.dropdown-btn:disabled {
  background: #F1F5F9;
  color: #94A3B8;
  cursor: not-allowed;
  opacity: 0.6;
}

.dropdown-btn svg {
  color: #64748B;
}

.dropdown-btn span {
  flex: 1;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-menu {
  position: absolute;
  z-index: 50;
  left: 0;
  right: 0;
  top: calc(100% + 6px);
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.dropdown-item {
  width: 100%;
  text-align: left;
  padding: 10px 16px;
  font-size: 14px;
  color: #1E293B;
  transition: all 150ms;
}

.dropdown-item:hover:not(:disabled) {
  background: #F1F5F9;
}

.dropdown-item--selected {
  background: rgba(37, 99, 235, 0.08);
  color: #2563EB;
  font-weight: 600;
}

.dropdown-item--disabled {
  color: #94A3B8;
  cursor: not-allowed;
}

.placeholder-box {
  width: 100%;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  background: #F1F5F9;
  color: #94A3B8;
  font-size: 14px;
  opacity: 0.5;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: not-allowed;
  user-select: none;
}

.placeholder-box svg {
  color: #94A3B8;
}

.empty-kp-box {
  width: 100%;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  background: #FFFFFF;
  color: #64748B;
  font-size: 14px;
  text-align: center;
  line-height: 1.6;
}

.link-btn {
  color: #2563EB;
  text-decoration: underline;
  text-underline-offset: 4px;
  font-weight: 500;
}

.kp-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kp-card {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 2px solid transparent;
  background: #FFFFFF;
  text-align: left;
  cursor: pointer;
  transition: all 150ms;
}

.kp-card:hover {
  background: #F8FAFC;
  border-color: rgba(37, 99, 235, 0.4);
}

.kp-card--selected {
  border-color: #2563EB;
  background: rgba(37, 99, 235, 0.04);
}

.kp-radio {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid #CBD5E1;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
  transition: all 150ms;
}

.kp-radio--selected {
  border-color: #2563EB;
  background: #2563EB;
}

.radio-inner {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #FFFFFF;
}

.kp-content {
  flex: 1;
  min-width: 0;
}

.kp-name {
  font-size: 15px;
  font-weight: 500;
  color: #1E293B;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}



.kp-summary {
  font-size: 13px;
  color: #64748B;
  margin-top: 4px;
  line-height: 1.5;
}

.greeting-preview {
  margin-top: 24px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(37, 99, 235, 0.04);
  border: 1px solid rgba(37, 99, 235, 0.1);
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.greeting-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #DBEAFE;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.greeting-content {
  flex: 1;
  min-width: 0;
}

.greeting-label {
  font-size: 12px;
  font-weight: 600;
  color: #2563EB;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.greeting-text {
  font-size: 14px;
  color: #1E40AF;
  line-height: 1.6;
  margin: 0;
}

.select-footer {
  position: sticky;
  bottom: 0;
  background: #FFFFFF;
  border-top: 1px solid #E2E8F0;
  padding: 16px;
}

.footer-inner {
  max-width: 480px;
  margin: 0 auto;
}

.start-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  transition: all 150ms;
}

.start-btn:not(:disabled) {
  background: #2563EB;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}

.start-btn:not(:disabled):hover {
  background: #1D4ED8;
}

.start-btn:not(:disabled):active {
  transform: scale(0.99);
}

.start-btn:disabled {
  background: #F1F5F9;
  color: #94A3B8;
  cursor: not-allowed;
}

.footer-hint {
  text-align: center;
  font-size: 13px;
  color: #94A3B8;
  margin: 8px 0 0 0;
}

.toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 12px 24px;
  background: rgba(15, 23, 42, 0.9);
  color: #FFFFFF;
  border-radius: 10px;
  font-size: 14px;
  z-index: 200;
}

.rotate-180 {
  transform: rotate(180deg);
}
</style>
