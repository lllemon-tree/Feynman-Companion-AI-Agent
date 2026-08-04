<script setup>
import { ref, watch, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { saveUserProfile, updateUserProfile } from '@/api/feynman'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  initialData: {
    type: Object,
    default: () => ({})
  },
  mode: {
    type: String, // 'create' | 'edit'
    default: 'create'
  }
})

const emit = defineEmits(['close', 'saved'])

const formData = reactive({
  exam_subject: '',
  exam_sub_category: '',
  preparation_stage: '',
  exam_type: '',
  pain_points: [],
  target_school: '',
  target_major: ''
})

const subjects = ['计算机', '政治', '数学', '英语', '专业课一', '专业课二', '其他']
const subCategories = ['408统考', '自命题']
const stages = ['基础', '强化', '冲刺']
const examTypes = ['应届', '二战', '在职']
const painPoints = ['概念理解困难', '输出薄弱', '知识碎片化', '盲目刷题', '自律性差']

const isComputerSubject = ref(false)

function selectSubject(subjectName) {
  formData.exam_subject = subjectName
  isComputerSubject.value = subjectName === '计算机'
  if (!isComputerSubject.value) {
    formData.exam_sub_category = ''
    subCatDropdownOpen.value = false
  }
  subjectDropdownOpen.value = false
}

function selectSubCategory(catName) {
  formData.exam_sub_category = catName
  subCatDropdownOpen.value = false
}

// 自定义下拉
const subjectDropdownOpen = ref(false)
const subCatDropdownOpen = ref(false)
const subjectDropdownRef = ref(null)
const subCatDropdownRef = ref(null)

function toggleSubjectDropdown() {
  subjectDropdownOpen.value = !subjectDropdownOpen.value
  if (subjectDropdownOpen.value) {
    subCatDropdownOpen.value = false
  }
}

function closeSubjectDropdown() {
  subjectDropdownOpen.value = false
}

function toggleSubCatDropdown() {
  subCatDropdownOpen.value = !subCatDropdownOpen.value
  if (subCatDropdownOpen.value) {
    subjectDropdownOpen.value = false
  }
}

function closeSubCatDropdown() {
  subCatDropdownOpen.value = false
}

function handleDropdownClickOutside(e) {
  if (subjectDropdownRef.value && !subjectDropdownRef.value.contains(e.target)) {
    subjectDropdownOpen.value = false
  }
  if (subCatDropdownRef.value && !subCatDropdownRef.value.contains(e.target)) {
    subCatDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDropdownClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDropdownClickOutside)
})

function getSelectedSubject() {
  return subjects.find(s => s === formData.exam_subject)
}

function getSelectedSubCat() {
  return subCategories.find(c => c === formData.exam_sub_category)
}

const isSubmitting = ref(false)

watch(() => props.visible, (newVal) => {
  if (newVal && props.mode === 'edit' && props.initialData) {
    // 填充已有数据
    formData.exam_subject = props.initialData.exam_subject || ''
    formData.exam_sub_category = props.initialData.exam_sub_category || ''
    formData.preparation_stage = props.initialData.preparation_stage || ''
    formData.exam_type = props.initialData.exam_type || ''
    formData.pain_points = props.initialData.pain_points || []
    formData.target_school = props.initialData.target_school || ''
    formData.target_major = props.initialData.target_major || ''
    isComputerSubject.value = formData.exam_subject === '计算机'
  } else if (newVal && props.mode === 'create') {
    // 重置表单
    formData.exam_subject = ''
    formData.exam_sub_category = ''
    formData.preparation_stage = ''
    formData.exam_type = ''
    formData.pain_points = []
    formData.target_school = ''
    formData.target_major = ''
    isComputerSubject.value = false
  }
})

function togglePainPoint(point) {
  const idx = formData.pain_points.indexOf(point)
  if (idx > -1) {
    formData.pain_points.splice(idx, 1)
  } else {
    formData.pain_points.push(point)
  }
}

function selectStage(stage) {
  formData.preparation_stage = stage
}

function selectExamType(type) {
  formData.exam_type = type
}

function closeModal() {
  emit('close')
}

async function handleSubmit() {
  isSubmitting.value = true
  try {
    const payload = { ...formData }
    
    if (props.mode === 'create') {
      await saveUserProfile(payload)
      // 标记已完成首次学情设置
      localStorage.setItem('feynman_profile_setup_done', 'true')
    } else {
      await updateUserProfile(payload)
    }
    
    emit('saved', payload)
    emit('close')
  } catch (e) {
    alert('保存失败: ' + e.message)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div v-if="visible" class="modal-overlay" @click.self="closeModal">
    <div class="modal-container">
      <header class="modal-header">
        <h2 class="modal-title">{{ mode === 'create' ? '完善你的学习画像' : '编辑学习画像' }}</h2>
        <button class="close-btn" @click="closeModal">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </header>

      <div class="modal-body">
        <div class="form-group">
          <label class="form-label">报考学科</label>
          <div ref="subjectDropdownRef" class="custom-dropdown">
            <button
              class="dropdown-trigger"
              :class="{ 'dropdown-trigger--active': subjectDropdownOpen }"
              @click.stop="toggleSubjectDropdown"
            >
              <template v-if="getSelectedSubject()">
                <span class="dropdown-selected-text">{{ getSelectedSubject() }}</span>
              </template>
              <template v-else>
                <span class="dropdown-placeholder">请选择学科</span>
              </template>
              <svg
                class="dropdown-chevron"
                :class="{ 'rotate-180': subjectDropdownOpen }"
                width="13" height="13" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="2.5"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            <div v-if="subjectDropdownOpen" class="dropdown-panel">
              <button
                v-for="subject in subjects"
                :key="subject"
                class="dropdown-item"
                :class="{ 'dropdown-item--active': formData.exam_subject === subject }"
                @click.stop="selectSubject(subject)"
              >
                <span class="dropdown-item-text">{{ subject }}</span>
                <svg
                  v-if="formData.exam_subject === subject"
                  width="14" height="14" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" stroke-width="2.5"
                  class="dropdown-item-check"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div v-if="isComputerSubject" class="form-group animate-in">
          <label class="form-label">计算机学科方向</label>
          <div ref="subCatDropdownRef" class="custom-dropdown">
            <button
              class="dropdown-trigger"
              :class="{ 'dropdown-trigger--active': subCatDropdownOpen }"
              @click.stop="toggleSubCatDropdown"
            >
              <template v-if="getSelectedSubCat()">
                <span class="dropdown-selected-text">{{ getSelectedSubCat() }}</span>
              </template>
              <template v-else>
                <span class="dropdown-placeholder">请选择方向</span>
              </template>
              <svg
                class="dropdown-chevron"
                :class="{ 'rotate-180': subCatDropdownOpen }"
                width="13" height="13" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="2.5"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            <div v-if="subCatDropdownOpen" class="dropdown-panel">
              <button
                v-for="cat in subCategories"
                :key="cat"
                class="dropdown-item"
                :class="{ 'dropdown-item--active': formData.exam_sub_category === cat }"
                @click.stop="selectSubCategory(cat)"
              >
                <span class="dropdown-item-text">{{ cat }}</span>
                <svg
                  v-if="formData.exam_sub_category === cat"
                  width="14" height="14" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" stroke-width="2.5"
                  class="dropdown-item-check"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">备考阶段</label>
          <div class="card-group">
            <button 
              v-for="stage in stages" 
              :key="stage"
              class="option-card"
              :class="{ 'option-card--active': formData.preparation_stage === stage }"
              @click="selectStage(stage)"
            >
              {{ stage }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">备考类型</label>
          <div class="card-group">
            <button 
              v-for="type in examTypes" 
              :key="type"
              class="option-card"
              :class="{ 'option-card--active': formData.exam_type === type }"
              @click="selectExamType(type)"
            >
              {{ type }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">核心痛点（可多选）</label>
          <div class="tag-group">
            <button 
              v-for="point in painPoints" 
              :key="point"
              class="option-tag"
              :class="{ 'option-tag--active': formData.pain_points.includes(point) }"
              @click="togglePainPoint(point)"
            >
              {{ point }}
            </button>
          </div>
        </div>
      </div>

      <footer class="modal-footer">
        <button 
          v-if="mode === 'create'" 
          class="btn btn-secondary" 
          @click="closeModal"
        >
          稍后填写
        </button>
        <button 
          v-else 
          class="btn btn-secondary" 
          @click="closeModal"
        >
          取消
        </button>
        <button 
          class="btn btn-primary" 
          :disabled="isSubmitting"
          @click="handleSubmit"
        >
          <span v-if="isSubmitting">保存中...</span>
          <span v-else>{{ mode === 'create' ? '保存并开始学习' : '保存修改' }}</span>
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-container {
  background: #FFFFFF;
  border-radius: 20px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #E2E8F0;
}

.modal-title {
  margin: 0;
  font-size: 18px;
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
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #475569;
}

.form-input,
.form-select {
  width: 100%;
  padding: 12px 16px;
  font-size: 14px;
  color: #1E293B;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  outline: none;
  transition: all 150ms;
  font-family: inherit;
}

.form-input:focus,
.form-select:focus {
  border-color: #2563EB;
  background: #FFFFFF;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.custom-dropdown {
  position: relative;
}

.dropdown-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
  background: #FFFFFF;
  font-size: 14px;
  font-weight: 500;
  color: #1E293B;
  transition: all 150ms;
  cursor: pointer;
  justify-content: space-between;
}

.dropdown-trigger:hover {
  background: #F8FAFC;
  border-color: #CBD5E1;
}

.dropdown-trigger--active {
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.dropdown-placeholder {
  color: #94A3B8;
  font-weight: 400;
}

.dropdown-selected-icon {
  font-size: 15px;
  line-height: 1;
}

.dropdown-selected-text {
  flex: 1;
  text-align: left;
}

.dropdown-chevron {
  color: #64748B;
  transition: transform 150ms ease;
  flex-shrink: 0;
}

.dropdown-panel {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 6px);
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  z-index: 1100;
  animation: panelFadeIn 0.15s ease-out;
}

@keyframes panelFadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dropdown-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  text-align: left;
  font-size: 14px;
  color: #475569;
  transition: all 120ms;
  cursor: pointer;
  position: relative;
}

.dropdown-item:hover {
  background: #F1F5F9;
  color: #1E293B;
}

.dropdown-item--active {
  background: rgba(37, 99, 235, 0.06);
  color: #2563EB;
  font-weight: 500;
}

.dropdown-item-icon {
  font-size: 15px;
  line-height: 1;
}

.dropdown-item-text {
  flex: 1;
}

.dropdown-item-check {
  color: #2563EB;
  flex-shrink: 0;
}

.card-group {
  display: flex;
  gap: 8px;
}

.animate-in {
  animation: panelFadeIn 0.2s ease-out;
}

.option-card {
  flex: 1;
  padding: 12px 16px;
  background: #F8FAFC;
  border: 2px solid #E2E8F0;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: #64748B;
  transition: all 150ms;
  cursor: pointer;
}

.option-card:hover {
  border-color: #CBD5E1;
  color: #475569;
  background: #F1F5F9;
}

.option-card--active {
  background: rgba(37, 99, 235, 0.08);
  border-color: #2563EB;
  color: #2563EB;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.option-tag {
  padding: 8px 14px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 20px;
  font-size: 13px;
  color: #64748B;
  transition: all 150ms;
}

.option-tag:hover {
  border-color: #CBD5E1;
}

.option-tag--active {
  background: rgba(37, 99, 235, 0.1);
  border-color: #2563EB;
  color: #2563EB;
  font-weight: 500;
}

.modal-footer {
  display: flex;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid #E2E8F0;
  background: #F8FAFC;
}

.btn {
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  transition: all 150ms;
}

.btn-primary {
  background: #2563EB;
  color: #FFFFFF;
}

.btn-primary:hover:not(:disabled) {
  background: #1D4ED8;
}

.btn-primary:disabled {
  background: #94A3B8;
  cursor: not-allowed;
}

.btn-secondary {
  background: #FFFFFF;
  color: #64748B;
  border: 1px solid #E2E8F0;
}

.btn-secondary:hover {
  background: #F1F5F9;
  color: #475569;
}
</style>