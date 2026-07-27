<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchSubjects,
  getKnowledgeTree,
  getMaterialStatus,
  retryMaterial,
  uploadMaterial
} from '@/api/feynman'

const router = useRouter()
const DEFAULT_SUBJECTS = ['计算机', '数学', '政治']
const subjects = ref(DEFAULT_SUBJECTS)
const selectedSubject = ref('计算机')
const subjectOpen = ref(false)
const nameInput = ref('')
const materials = ref([])
const isUploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')
const dropZoneActive = ref(false)
const fileInput = ref(null)
const dragCounterRef = ref(0)

const toastMessage = ref('')
const showToast = ref(false)

const STEP_LABELS = {
  parsing: '解析中',
  chunking: '分块中',
  extracting: '抽取中',
  generating: 'rubric生成中',
}

const pollingTimers = ref(new Map())

async function loadMaterials() {
  try {
    const tree = await getKnowledgeTree(selectedSubject.value)
    materials.value = tree.map(m => ({
      id: m.material_id,
      name: m.title,
      status: m.status,
      step: m.step,
      progress: m.progress * 100,
      error: m.error || null
    }))

    materials.value.forEach(m => {
      if (['parsing', 'chunking', 'extracting', 'generating'].includes(m.status)) {
        startStatusPolling(m.id)
      }
    })
  } catch (e) {
    showToastMsg(e.message)
  }
}

function handleDrop(e) {
  e.preventDefault()
  dragCounterRef.value = 0
  dropZoneActive.value = false
  const file = e.dataTransfer.files[0]
  if (file) validateAndUpload(file)
}

function handleDragEnter(e) {
  e.preventDefault()
  dragCounterRef.value++
  dropZoneActive.value = true
}

function handleDragLeave(e) {
  e.preventDefault()
  dragCounterRef.value--
  if (dragCounterRef.value <= 0) {
    dragCounterRef.value = 0
    dropZoneActive.value = false
  }
}

function handleDragOver(e) {
  e.preventDefault()
}

function handleClickDropZone() {
  if (!isUploading.value) {
    fileInput.value?.click()
  }
}

function handleFileInputChange(e) {
  const file = e.target.files?.[0]
  if (file) validateAndUpload(file)
  e.target.value = ''
}

function validateAndUpload(file) {
  if (isUploading.value) return
  const isPdf = file.name.toLowerCase().endsWith('.pdf') && file.type === 'application/pdf'
  if (!isPdf) {
    showToastMsg('仅支持文字版PDF文件')
    return
  }
  if (file.size > 50 * 1024 * 1024) {
    uploadError.value = '文件超过50MB大小限制'
    return
  }
  startUpload(file)
}

async function startUpload(file) {
  isUploading.value = true
  uploadProgress.value = 0
  uploadError.value = ''
  
  try {
    const result = await uploadMaterial(
      file,
      selectedSubject.value,
      nameInput.value.trim(),
      (percent) => {
        uploadProgress.value = percent
      }
    )

    isUploading.value = false

    const newMaterial = {
      id: result.material_id,
      name: nameInput.value.trim() || file.name,
      status: result.status || 'parsing',
      step: result.step || 'parsing',
      progress: (result.progress || 0) * 100,
      error: null
    }
    materials.value.unshift(newMaterial)
    startStatusPolling(newMaterial.id)
  } catch (e) {
    isUploading.value = false
    uploadError.value = e.message || '上传失败，请重试'
  }
}

function startStatusPolling(materialId) {
  if (pollingTimers.value.has(materialId)) {
    clearInterval(pollingTimers.value.get(materialId))
  }
  
  const timer = setInterval(async () => {
    try {
      const status = await getMaterialStatus(materialId)
      updateMaterial(materialId, {
        status: status.status,
        step: status.step,
        progress: status.progress == null ? undefined : status.progress * 100,
        error: status.error || null
      })
      
      if (status.status === 'done' || status.status === 'failed') {
        stopStatusPolling(materialId)
      }
    } catch (e) {
      stopStatusPolling(materialId)
    }
  }, 2000)
  
  pollingTimers.value.set(materialId, timer)
}

function stopStatusPolling(materialId) {
  const timer = pollingTimers.value.get(materialId)
  if (timer) {
    clearInterval(timer)
    pollingTimers.value.delete(materialId)
  }
}

function updateMaterial(id, patch) {
  materials.value = materials.value.map(m => m.id === id ? { ...m, ...patch } : m)
}

async function handleRetry(id) {
  try {
    await retryMaterial(id)
    updateMaterial(id, { status: 'parsing', step: '等待重新解析', progress: 0, error: undefined })
    startStatusPolling(id)
  } catch (e) {
    showToastMsg(e.message || '重试失败')
  }
}

function handleMaterialClick(m) {
  if (m.status !== 'done') return
  router.push(`/knowledge?materialId=${m.id}&subject=${selectedSubject.value}&name=${encodeURIComponent(m.name)}`)
}

function goToSelectPage() {
  router.push('/select')
}

function showToastMsg(msg) {
  toastMessage.value = msg
  showToast.value = true
  setTimeout(() => {
    showToast.value = false
  }, 3000)
}

function handleSubjectChange(s) {
  selectedSubject.value = s
  subjectOpen.value = false
  pollingTimers.value.forEach(timer => clearInterval(timer))
  pollingTimers.value.clear()
  loadMaterials()
}

onMounted(async () => {
  try {
    const storedSubjects = await fetchSubjects()
    subjects.value = [...new Set([...DEFAULT_SUBJECTS, ...storedSubjects])]
  } catch (e) {
    console.warn('加载科目列表失败，使用默认科目:', e)
  }
  loadMaterials()
})
</script>

<template>
  <div class="upload-page">
    <header class="upload-header">
      <span class="page-title">费曼伴学</span>
      <div class="header-actions">
        <div class="subject-dropdown">
          <button
            class="subject-btn"
            @click="subjectOpen = !subjectOpen"
            @blur="setTimeout(() => subjectOpen = false, 150)"
          >
            {{ selectedSubject }}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'rotate-180': subjectOpen }">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          <div v-if="subjectOpen" class="subject-menu">
            <button
              v-for="s in subjects"
              :key="s"
              class="subject-item"
              :class="{ 'subject-item--selected': s === selectedSubject }"
              @click="handleSubjectChange(s)"
            >
              {{ s }}
            </button>
          </div>
        </div>
        <button class="select-entry-btn" @click="goToSelectPage">
          选择知识点
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </header>

    <main class="upload-main">
      <h1 class="main-title">上传教材PDF</h1>
      <label class="name-field">
        <span>教材名称</span>
        <input
          v-model="nameInput"
          type="text"
          placeholder="留空则使用PDF文件名"
          :disabled="isUploading"
        />
      </label>

      <div
        class="drop-zone"
        :class="{ 'drop-zone--active': dropZoneActive, 'drop-zone--uploading': isUploading }"
        @drop="handleDrop"
        @dragenter="handleDragEnter"
        @dragleave="handleDragLeave"
        @dragover="handleDragOver"
        @click="handleClickDropZone"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,application/pdf"
          class="file-input"
          @change="handleFileInputChange"
        />

        <template v-if="isUploading">
          <div class="uploading-content">
            <div class="upload-icon-wrapper">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>
            <div class="upload-filename">{{ uploadProgress > 0 ? '正在上传...' : '' }}</div>
            <div class="upload-progress-bar">
              <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <div class="upload-percent">文件上传中 {{ uploadProgress }}%</div>
          </div>
        </template>

        <template v-else>
          <div class="drop-icon-wrapper" :class="{ 'drop-icon-wrapper--active': dropZoneActive }">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" :class="{ 'drop-icon--active': dropZoneActive }">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <div class="drop-text">拖拽教材PDF到此处 / 点击选择文件</div>
          <div class="drop-hint">仅支持文字版PDF文件，文件大小上限50MB</div>
        </template>
      </div>

      <div v-if="uploadError" class="upload-error">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        {{ uploadError }}
        <button class="retry-link" @click="fileInput?.click()">重新上传</button>
      </div>

      <div class="materials-section">
        <div class="section-header">
          <h2 class="section-title">已上传教材 · {{ selectedSubject }}</h2>
          <span v-if="materials.length > 0" class="section-count">{{ materials.length }} 份</span>
        </div>

        <div v-if="materials.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <p>暂无上传教材，请拖拽PDF文件上传</p>
        </div>

        <div v-else class="material-list">
          <div
            v-for="m in materials"
            :key="m.id"
            class="material-item"
            :class="{
              'material-item--done': m.status === 'done',
              'material-item--failed': m.status === 'failed',
              'material-item--processing': ['parsing', 'chunking', 'extracting', 'generating'].includes(m.status)
            }"
            @click="handleMaterialClick(m)"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" :class="{ 'material-icon--done': m.status === 'done' }">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>

            <div class="material-info">
              <div class="material-name">{{ m.name }}</div>
              
              <template v-if="['parsing', 'chunking', 'extracting', 'generating'].includes(m.status)">
                <div class="processing-info">
                  <span class="processing-text">{{ STEP_LABELS[m.step] || m.step }}</span>
                  <span class="processing-percent">{{ m.progress }}%</span>
                </div>
                <div class="processing-bar">
                  <div class="bar-fill" :style="{ width: m.progress + '%' }"></div>
                </div>
              </template>

              <template v-else-if="m.status === 'done'">
                <div class="done-info">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span>已完成 · PDF已切片入库 · 点击查看知识点</span>
                </div>
              </template>

              <template v-else-if="m.status === 'failed'">
                <div class="failed-info">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{{ m.error || '解析失败' }}</span>
                </div>
              </template>
            </div>

            <svg v-if="['parsing', 'chunking', 'extracting', 'generating'].includes(m.status)" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
              <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
            </svg>

            <button
              v-if="m.status === 'failed'"
              class="retry-btn"
              @click.stop="handleRetry(m.id)"
            >
              重试解析
            </button>
          </div>
        </div>
      </div>
    </main>

    <div v-if="showToast" class="toast">{{ toastMessage }}</div>
  </div>
</template>

<style scoped>
.upload-page {
  min-height: 100vh;
  background: #F8FAFC;
  display: flex;
  flex-direction: column;
  font-family: 'Noto Sans SC', 'Inter', sans-serif;
}

.upload-header {
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.select-entry-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #2563EB;
  border-radius: 8px;
  background: #2563EB;
  color: #FFFFFF;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 150ms, border-color 150ms;
}

.select-entry-btn:hover {
  border-color: #1D4ED8;
  background: #1D4ED8;
}

.subject-dropdown {
  position: relative;
}

.subject-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #E2E8F0;
  background: #FFFFFF;
  font-size: 14px;
  font-weight: 500;
  color: #1E293B;
  transition: all 150ms;
}

.subject-btn:hover {
  background: #F1F5F9;
}

.subject-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 112px;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  z-index: 40;
}

.subject-item {
  width: 100%;
  text-align: left;
  padding: 10px 16px;
  font-size: 14px;
  color: #1E293B;
  transition: all 150ms;
}

.subject-item:hover:not(.subject-item--selected) {
  background: #F1F5F9;
}

.subject-item--selected {
  background: rgba(37, 99, 235, 0.08);
  color: #2563EB;
  font-weight: 600;
}

.upload-main {
  flex: 1;
  padding: 32px 16px;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.main-title {
  font-size: 20px;
  font-weight: 600;
  color: #1E293B;
  margin: 0;
}

.name-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

.name-field input {
  width: 100%;
  padding: 11px 13px;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  background: #FFFFFF;
  color: #1E293B;
  font: inherit;
  font-weight: 400;
  outline: none;
  transition: border-color 150ms, box-shadow 150ms;
}

.name-field input:focus {
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.name-field input:disabled {
  background: #F1F5F9;
  color: #94A3B8;
}

.drop-zone {
  border: 2px dashed #CBD5E1;
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  cursor: pointer;
  transition: all 200ms;
  background: #FFFFFF;
  min-height: 196px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drop-zone:hover:not(.drop-zone--uploading) {
  border-color: rgba(37, 99, 235, 0.5);
  background: rgba(37, 99, 235, 0.02);
}

.drop-zone--active {
  border-color: #2563EB;
  background: rgba(37, 99, 235, 0.04);
}

.drop-zone--uploading {
  pointer-events: none;
}

.file-input {
  display: none;
}

.drop-icon-wrapper {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: #F1F5F9;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  transition: all 200ms;
}

.drop-icon-wrapper--active {
  background: rgba(37, 99, 235, 0.15);
  transform: scale(1.1);
}

.drop-icon {
  color: #94A3B8;
}

.drop-icon--active {
  color: #2563EB;
}

.drop-text {
  font-size: 15px;
  font-weight: 500;
  color: #1E293B;
  margin-bottom: 8px;
}

.drop-hint {
  font-size: 13px;
  color: #64748B;
}

.uploading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.upload-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: rgba(37, 99, 235, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2563EB;
}

.upload-filename {
  font-size: 14px;
  color: #64748B;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-progress-bar {
  width: 100%;
  height: 8px;
  background: #E2E8F0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #2563EB;
  transition: width 300ms ease-out;
}

.upload-percent {
  font-size: 14px;
  font-weight: 600;
  color: #2563EB;
}

.upload-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: #DC2626;
  font-size: 14px;
}

.retry-link {
  font-size: 13px;
  font-weight: 600;
  color: #DC2626;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.materials-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.section-count {
  font-size: 12px;
  color: #94A3B8;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 56px;
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

.material-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.material-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  transition: all 150ms;
}

.material-item--done {
  cursor: pointer;
}

.material-item--done:hover {
  border-color: rgba(37, 99, 235, 0.4);
  background: rgba(37, 99, 235, 0.02);
}

.material-icon--done {
  color: rgba(37, 99, 235, 0.6);
}

.material-info {
  flex: 1;
  min-width: 0;
}

.material-name {
  font-size: 14px;
  font-weight: 500;
  color: #1E293B;
  margin-bottom: 4px;
}

.processing-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.processing-text {
  font-size: 13px;
  color: #64748B;
}

.processing-percent {
  font-size: 13px;
  color: #2563EB;
  font-weight: 500;
}

.processing-bar {
  height: 6px;
  background: #E2E8F0;
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #2563EB;
  transition: width 700ms;
}

.done-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #10B981;
  font-size: 13px;
  font-weight: 500;
}

.failed-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #EF4444;
  font-size: 13px;
}

.spinner {
  animation: spin 1s linear infinite;
  color: #2563EB;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.retry-btn {
  padding: 6px 12px;
  border: 1px solid rgba(37, 99, 235, 0.3);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #2563EB;
  transition: all 150ms;
}

.retry-btn:hover {
  background: rgba(37, 99, 235, 0.05);
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
