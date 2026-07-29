<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { getKnowledgeTree, getUserProfile, getGaps, getGapsStats, updateGapStatus, getReports, getReportDetail, getSessionList, getSessionDetail } from '@/api/feynman'
import ProfileSetupModal from '@/components/ProfileSetupModal.vue'
import ReportDrawer from '@/components/ReportDrawer.vue'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref('profile')
const loading = ref(false)

// 学情档案
const userProfile = ref(null)
const showProfileModal = ref(false)
const isEditingProfile = ref(false)

// 知识漏洞
const gaps = ref([])
const gapStats = ref({})
const activeGapStatus = ref('open')
const loadingGaps = ref(false)

// 历史报告
const reports = ref([])
const showReportDetail = ref(false)
const selectedReport = ref(null)
const reportDetailLoading = ref(false)

// 我的教材
const materials = ref([])
const loadingMaterials = ref(false)

// 历史会话
const sessions = ref([])
const loadingSessions = ref(false)
const showSessionDetail = ref(false)
const selectedSession = ref(null)
const sessionDetailLoading = ref(false)

const tabs = [
  { key: 'profile', label: '学情档案', icon: 'user' },
  { key: 'gaps', label: '知识漏洞', icon: 'alert' },
  { key: 'sessions', label: '历史会话', icon: 'chat' },
  { key: 'reports', label: '历史报告', icon: 'chart' },
  { key: 'materials', label: '我的教材', icon: 'book' }
]

const gapStatusTabs = [
  { key: 'open', label: '待复习', color: '#EF4444' },
  { key: 'reviewing', label: '复习中', color: '#F59E0B' },
  { key: 'resolved', label: '已掌握', color: '#10B981' }
]

const isLoggedIn = computed(() => authStore.isLoggedIn)
const username = computed(() => authStore.username)

async function loadUserProfile() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const data = await getUserProfile()
    userProfile.value = data
  } catch (e) {
    userProfile.value = null
  } finally {
    loading.value = false
  }
}

async function loadGaps() {
  if (!isLoggedIn.value) return
  loadingGaps.value = true
  try {
    const [gapsData, statsData] = await Promise.all([
      getGaps(activeGapStatus.value),
      getGapsStats()
    ])
    gaps.value = gapsData.items || []
    gapStats.value = statsData
  } catch (e) {
    gaps.value = []
    gapStats.value = {}
  } finally {
    loadingGaps.value = false
  }
}

async function updateGapStatusAction(gapId, newStatus) {
  try {
    await updateGapStatus(gapId, newStatus)
    // 更新成功后重新加载
    await loadGaps()
  } catch (e) {
    alert('更新失败: ' + e.message)
  }
}

async function loadSessions() {
  if (!isLoggedIn.value) return
  loadingSessions.value = true
  try {
    const data = await getSessionList()
    sessions.value = data || []
  } catch (e) {
    sessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

async function viewSessionDetail(session) {
  selectedSession.value = session
  showSessionDetail.value = true
  sessionDetailLoading.value = true
  try {
    const detail = await getSessionDetail(session.session_id)
    selectedSession.value = detail
  } catch (e) {
    console.error('获取会话详情失败', e)
  } finally {
    sessionDetailLoading.value = false
  }
}

function continueSession(session) {
  // 跳转到聊天页面，携带会话ID和KP信息
  router.push({
    path: '/home',
    query: {
      sessionId: session.session_id,
      kpName: session.kp_name,
      materialName: session.material_title
    }
  })
}

async function loadReports() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const data = await getReports()
    reports.value = data.items || []
  } catch (e) {
    reports.value = []
  } finally {
    loading.value = false
  }
}

async function viewReportDetail(report) {
  selectedReport.value = report
  showReportDetail.value = true
  reportDetailLoading.value = true
  try {
    const detail = await getReportDetail(report.report_id)
    // 详情接口返回 dimensions_full，ReportDrawer 需要 dimensions 字段
    selectedReport.value = {
      ...detail,
      dimensions: detail.dimensions_full || report.dimensions
    }
  } catch (e) {
    console.error('获取报告详情失败', e)
    selectedReport.value = report
  } finally {
    reportDetailLoading.value = false
  }
}

async function loadMaterials() {
  loadingMaterials.value = true
  try {
    const USE_MOCK = import.meta.env.VITE_USE_MATERIAL_MOCK !== 'false'
    
    if (USE_MOCK) {
      await delay(500)
      materials.value = [
        {
          id: 'mat-demo',
          name: '数据结构教材.pdf',
          subject: '计算机',
          chapters: 2,
          kps: 3,
          createdAt: '2026-07-20'
        }
      ]
    } else {
      const tree = await getKnowledgeTree('computer')
      materials.value = tree.map(m => ({
        id: m.material_id,
        name: m.title + '.pdf',
        subject: '计算机',
        chapters: m.chapters.length,
        kps: m.chapters.reduce((sum, ch) => sum + ch.knowledge_points.length, 0),
        createdAt: '2026-07-20'
      }))
    }
  } catch (e) {
    materials.value = []
  } finally {
    loadingMaterials.value = false
  }
}

function handleTabChange(key) {
  activeTab.value = key
  if (key === 'profile') {
    loadUserProfile()
  } else if (key === 'gaps') {
    loadGaps()
  } else if (key === 'sessions') {
    loadSessions()
  } else if (key === 'reports') {
    loadReports()
  } else if (key === 'materials') {
    loadMaterials()
  }
}

function handleGapStatusChange(status) {
  activeGapStatus.value = status
  loadGaps()
}

function openProfileModal(editing = false) {
  isEditingProfile.value = editing
  showProfileModal.value = true
}

function closeProfileModal() {
  showProfileModal.value = false
}

async function handleProfileSaved() {
  await loadUserProfile()
}

function goToMaterialKnowledge(material) {
  router.push(`/knowledge?materialId=${material.id}&subject=${material.subject}&name=${encodeURIComponent(material.name)}`)
}

function goToUpload() {
  router.push('/upload')
}

function goBack() {
  router.push('/select')
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

onMounted(() => {
  // 根据当前tab加载数据
  if (activeTab.value === 'profile') {
    loadUserProfile()
  } else if (activeTab.value === 'gaps') {
    loadGaps()
  } else if (activeTab.value === 'sessions') {
    loadSessions()
  } else if (activeTab.value === 'reports') {
    loadReports()
  } else if (activeTab.value === 'materials') {
    loadMaterials()
  }
})
</script>

<template>
  <div class="profile-page">
    <header class="profile-header">
      <button class="back-btn" @click="goBack">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        返回
      </button>
      <h1 class="page-title">个人中心</h1>
      <div class="header-placeholder"></div>
    </header>

    <main class="profile-main">
      <!-- 用户信息卡片 -->
      <div class="user-card">
        <div class="user-avatar-large">
          <span v-if="username" class="avatar-letter">{{ username.charAt(0).toUpperCase() }}</span>
          <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <div class="user-info">
          <h2 class="user-name">{{ isLoggedIn ? username : '游客用户' }}</h2>
          <p class="user-status">{{ isLoggedIn ? '已登录' : '游客模式' }}</p>
        </div>
        <button v-if="!isLoggedIn" class="login-prompt-btn" @click="router.push('/login')">
          去登录
        </button>
      </div>

      <!-- Tab 切换 -->
      <div class="tabs-container">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ 'tab-btn--active': activeTab === tab.key }"
          @click="handleTabChange(tab.key)"
        >
          <svg v-if="tab.icon === 'user'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <svg v-else-if="tab.icon === 'alert'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <svg v-else-if="tab.icon === 'chart'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          <svg v-else-if="tab.icon === 'chat'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <svg v-else-if="tab.icon === 'book'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          <span>{{ tab.label }}</span>
        </button>
      </div>

      <!-- 学情档案 Tab -->
      <div v-if="activeTab === 'profile'" class="tab-content">
        <div v-if="loading" class="loading-state">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
            <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
          </svg>
          <p>加载中...</p>
        </div>

        <!-- 未登录提示 -->
        <div v-else-if="!isLoggedIn" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <p>登录后查看和编辑你的学习画像</p>
          <button class="upload-btn" @click="router.push('/login')">
            去登录
          </button>
        </div>

        <!-- 无数据状态 -->
        <div v-else-if="!userProfile || (!userProfile.exam_subject && !userProfile.preparation_stage)" class="profile-card">
          <div class="profile-empty">
            <div class="empty-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <p class="empty-title">尚未完善学习画像</p>
            <p class="empty-desc">完善画像可以获得更个性化的学习建议</p>
            <button class="upload-btn" @click="openProfileModal(false)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>开始完善</span>
            </button>
          </div>
        </div>

        <!-- 有数据状态 -->
        <div v-else class="profile-card">
          <div class="profile-card-header">
            <h3 class="profile-card-title">我的学习画像</h3>
            <button class="edit-btn" @click="openProfileModal(true)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
              <span>编辑</span>
            </button>
          </div>
          
          <div class="profile-info-list">
            <div class="info-item" v-if="userProfile.exam_subject">
              <span class="info-label">报考学科</span>
              <span class="info-value">{{ userProfile.exam_subject }}</span>
            </div>
            <div class="info-item" v-if="userProfile.exam_sub_category">
              <span class="info-label">专业方向</span>
              <span class="info-value">{{ userProfile.exam_sub_category }}</span>
            </div>
            <div class="info-item" v-if="userProfile.preparation_stage">
              <span class="info-label">备考阶段</span>
              <span class="info-value">{{ userProfile.preparation_stage }}</span>
            </div>
            <div class="info-item" v-if="userProfile.exam_type">
              <span class="info-label">备考类型</span>
              <span class="info-value">{{ userProfile.exam_type }}</span>
            </div>
            <div class="info-item" v-if="userProfile.pain_points && userProfile.pain_points.length > 0">
              <span class="info-label">核心痛点</span>
              <div class="pain-points">
                <span v-for="point in userProfile.pain_points" :key="point" class="pain-tag">
                  {{ point }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 知识漏洞 Tab -->
      <div v-if="activeTab === 'gaps'" class="tab-content">
        <!-- 状态筛选 Tab -->
        <div class="gap-status-tabs">
          <button
            v-for="status in gapStatusTabs"
            :key="status.key"
            class="gap-status-tab"
            :class="{ 'gap-status-tab--active': activeGapStatus === status.key }"
            @click="handleGapStatusChange(status.key)"
          >
            {{ status.label }}
            <span class="gap-count" v-if="gapStats.by_status && gapStats.by_status[status.key]">
              {{ gapStats.by_status[status.key] }}
            </span>
          </button>
        </div>

        <div v-if="loadingGaps" class="loading-state">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
            <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
          </svg>
          <p>加载中...</p>
        </div>

        <!-- 未登录 -->
        <div v-else-if="!isLoggedIn" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            </svg>
          </div>
          <p>登录后查看你的知识漏洞</p>
          <button class="upload-btn" @click="router.push('/login')">
            去登录
          </button>
        </div>

        <!-- 空状态 -->
        <div v-else-if="gaps.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <polyline points="22 11 18 11 15 21 9 3 6 11 2 11" />
            </svg>
          </div>
          <p>暂无{{ gapStatusTabs.find(s => s.key === activeGapStatus)?.label }}的漏洞</p>
          <button class="start-btn" @click="router.push('/select')">
            开始学习
          </button>
        </div>

        <!-- 漏洞列表 -->
        <div v-else class="gaps-list">
          <div
            v-for="gap in gaps"
            :key="gap.gap_id"
            class="gap-card"
          >
            <div class="gap-header">
              <span class="gap-kp-name">{{ gap.kp_name }}</span>
              <span class="gap-dimension-tag" :class="getDimensionClass(gap.dimension)">
                {{ gap.dimension }}
              </span>
            </div>
            
            <div class="gap-body">
              <p class="gap-description">{{ gap.gap_description }}</p>
              
              <div class="gap-meta">
                <div class="gap-score">
                  <span class="score-current">{{ gap.score }}</span>
                  <span class="score-total">/10</span>
                </div>
                <div class="gap-severity">
                  <span v-for="i in 5" :key="i" class="star" :class="{ 'star--active': i <= gap.severity }">★</span>
                </div>
                <div class="gap-date">{{ formatDate(gap.created_at) }}</div>
              </div>
            </div>

            <div class="gap-actions">
              <button 
                v-if="gap.status === 'open'" 
                class="action-btn action-btn--review"
                @click="updateGapStatusAction(gap.gap_id, 'reviewing')"
              >
                开始复习
              </button>
              <button 
                v-if="gap.status === 'reviewing'" 
                class="action-btn action-btn--master"
                @click="updateGapStatusAction(gap.gap_id, 'resolved')"
              >
                标记已掌握
              </button>
              <button 
                v-if="gap.status === 'resolved'" 
                class="action-btn action-btn--reopen"
                @click="updateGapStatusAction(gap.gap_id, 'open')"
              >
                重新打开
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史会话 Tab -->
      <div v-if="activeTab === 'sessions'" class="tab-content">
        <div v-if="loadingSessions" class="loading-state">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
            <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
          </svg>
          <p>加载中...</p>
        </div>

        <!-- 未登录 -->
        <div v-else-if="!isLoggedIn" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <p>登录后查看历史会话</p>
          <button class="upload-btn" @click="router.push('/login')">
            去登录
          </button>
        </div>

        <!-- 空状态 -->
        <div v-else-if="sessions.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <p>暂无历史会话，快去选择一个知识点开始讲解吧</p>
          <button class="start-btn" @click="router.push('/select')">
            开始学习
          </button>
        </div>

        <!-- 会话列表 -->
        <div v-else class="sessions-list">
          <div
            v-for="session in sessions"
            :key="session.session_id"
            class="session-card"
          >
            <div class="session-header">
              <div class="session-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div class="session-info">
                <div class="session-kp-name">{{ session.kp_name }}</div>
                <div class="session-meta">
                  <span>{{ session.material_title }}</span>
                  <span class="session-dot">·</span>
                  <span>{{ formatDate(session.created_at) }}</span>
                </div>
              </div>
            </div>
            <div class="session-actions">
              <button class="action-btn action-btn--view" @click="viewSessionDetail(session)">
                查看详情
              </button>
              <button class="action-btn action-btn--continue" @click="continueSession(session)">
                继续对话
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史报告 Tab -->
      <div v-if="activeTab === 'reports'" class="tab-content">
        <div v-if="loading" class="loading-state">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
            <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
          </svg>
          <p>加载中...</p>
        </div>

        <!-- 未登录 -->
        <div v-else-if="!isLoggedIn" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
          </div>
          <p>登录后查看历史报告</p>
          <button class="upload-btn" @click="router.push('/login')">
            去登录
          </button>
        </div>

        <!-- 空状态 -->
        <div v-else-if="reports.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <p>暂无历史报告，快去选择一个知识点开始讲解吧</p>
          <button class="start-btn" @click="router.push('/select')">
            开始学习
          </button>
        </div>

        <!-- 报告列表 -->
        <div v-else class="reports-list">
          <div
            v-for="report in reports"
            :key="report.report_id"
            class="report-card"
            @click="viewReportDetail(report)"
          >
            <div class="report-header">
              <span class="report-kp-name">{{ report.kp_name }}</span>
              <div class="report-score-badge">
                <span class="score-value">{{ report.total_score }}</span>
                <span class="score-max">/40</span>
              </div>
            </div>
            
            <div class="report-dimensions">
              <div 
                v-for="dim in report.dimensions" 
                :key="dim.name" 
                class="dim-bar"
              >
                <span class="dim-name">{{ dim.name }}</span>
                <div class="dim-progress">
                  <div 
                    class="dim-fill" 
                    :style="{ width: (dim.score / 10 * 100) + '%' }"
                    :class="getScoreClass(dim.score)"
                  ></div>
                </div>
                <span class="dim-score">{{ dim.score }}</span>
              </div>
            </div>

            <div class="report-footer">
              <span class="report-material">{{ report.material_name }}</span>
              <span class="report-date">{{ formatDate(report.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 我的教材 Tab -->
      <div v-if="activeTab === 'materials'" class="tab-content">
        <div v-if="loadingMaterials" class="loading-state">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
            <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
          </svg>
          <p>加载中...</p>
        </div>

        <!-- 未登录 -->
        <div v-else-if="!isLoggedIn" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </div>
          <p>登录后查看和管理你的教材</p>
          <button class="upload-btn" @click="router.push('/login')">
            去登录
          </button>
        </div>

        <!-- 空状态 -->
        <div v-else-if="materials.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <p>暂无教材</p>
          <button class="upload-btn" @click="goToUpload">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span>去上传教材</span>
          </button>
        </div>

        <!-- 教材列表 -->
        <div v-else class="materials-list">
          <div
            v-for="material in materials"
            :key="material.id"
            class="material-card"
            @click="goToMaterialKnowledge(material)"
          >
            <div class="material-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <div class="material-info">
              <div class="material-name">{{ material.name }}</div>
              <div class="material-meta">
                <span>{{ material.chapters }} 章节</span>
                <span>·</span>
                <span>{{ material.kps }} 知识点</span>
              </div>
            </div>
            <div class="material-date">{{ material.createdAt }}</div>
          </div>
        </div>
      </div>
    </main>

    <!-- 学情设置弹窗 -->
    <ProfileSetupModal
      :visible="showProfileModal"
      :mode="isEditingProfile ? 'edit' : 'create'"
      :initial-data="userProfile || {}"
      @close="closeProfileModal"
      @saved="handleProfileSaved"
    />

    <!-- 报告详情弹窗 -->
    <ReportDrawer
      :open="showReportDetail"
      :report="selectedReport"
      @close="showReportDetail = false"
    />

    <!-- 会话详情弹窗 -->
    <div v-if="showSessionDetail" class="session-drawer-overlay" @click.self="showSessionDetail = false">
      <div class="session-drawer">
        <div class="session-drawer-header">
          <h3 class="session-drawer-title">会话详情</h3>
          <button class="close-btn" @click="showSessionDetail = false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div class="session-drawer-body">
          <div v-if="sessionDetailLoading" class="loading-state">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
              <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
            </svg>
            <p>加载中...</p>
          </div>
          <div v-else-if="selectedSession" class="session-detail-content">
            <div class="detail-section">
              <div class="detail-row">
                <span class="detail-label">知识点</span>
                <span class="detail-value">{{ selectedSession.kp_name }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">教材</span>
                <span class="detail-value">{{ selectedSession.material_title }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">创建时间</span>
                <span class="detail-value">{{ formatDate(selectedSession.created_at) }}</span>
              </div>
            </div>
            <div class="detail-section">
              <h4 class="detail-section-title">对话历史</h4>
              <div v-if="selectedSession.chat_history && selectedSession.chat_history.length > 0" class="chat-history">
                <div
                  v-for="(msg, idx) in selectedSession.chat_history"
                  :key="idx"
                  class="chat-message"
                  :class="msg.role"
                >
                  <div class="chat-avatar">
                    <svg v-if="msg.role === 'user'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                    <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="5" y="8" width="14" height="10" rx="2" />
                      <rect x="9" y="11" width="2" height="2" rx="0.5" />
                      <rect x="13" y="11" width="2" height="2" rx="0.5" />
                    </svg>
                  </div>
                  <div class="chat-bubble">{{ msg.content }}</div>
                </div>
              </div>
              <div v-else class="empty-chat">
                <p>暂无对话历史</p>
              </div>
            </div>
          </div>
        </div>
        <div class="session-drawer-footer">
          <button class="btn btn-secondary" @click="showSessionDetail = false">关闭</button>
          <button
            v-if="selectedSession"
            class="btn btn-primary"
            @click="continueSession(selectedSession)"
          >
            继续对话
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  methods: {
    getDimensionClass(dimension) {
      const map = {
        '理解深度': 'dim-deep',
        '表达完整性': 'dim-complete',
        '逻辑连贯性': 'dim-logic',
        '结构化能力': 'dim-struct',
        '原理证明': 'dim-proof'
      }
      return map[dimension] || 'dim-default'
    },
    getScoreClass(score) {
      if (score >= 8) return 'score-high'
      if (score >= 6) return 'score-mid'
      return 'score-low'
    },
    formatDate(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      return date.toLocaleDateString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    }
  }
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: #F8FAFC;
  display: flex;
  flex-direction: column;
  font-family: 'Noto Sans SC', 'Inter', sans-serif;
}

.profile-header {
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

.page-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
}

.header-placeholder {
  width: 60px;
}

.profile-main {
  flex: 1;
  padding: 24px 16px;
  max-width: 600px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 用户卡片 */
.user-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #FFFFFF;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
}

.user-avatar-large {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  font-size: 24px;
  font-weight: 600;
}

.avatar-letter {
  text-transform: uppercase;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
  color: #1E293B;
}

.user-status {
  margin: 0;
  font-size: 13px;
  color: #64748B;
}

.login-prompt-btn {
  padding: 8px 16px;
  border-radius: 10px;
  background: #2563EB;
  color: #FFFFFF;
  font-size: 14px;
  font-weight: 600;
  transition: all 150ms;
}

.login-prompt-btn:hover {
  background: #1D4ED8;
}

/* Tab 容器 */
.tabs-container {
  display: flex;
  gap: 8px;
  background: #FFFFFF;
  padding: 6px;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 8px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  color: #64748B;
  transition: all 150ms;
}

.tab-btn--active {
  background: #2563EB;
  color: #FFFFFF;
}

.tab-btn--active svg {
  color: #FFFFFF;
}

.tab-content {
  flex: 1;
}

/* 加载和空状态 */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
  gap: 12px;
  background: #FFFFFF;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
}

.loading-state .spinner {
  animation: spin 1s linear infinite;
  color: #2563EB;
}

.loading-state p,
.empty-state p {
  margin: 0;
  font-size: 14px;
  color: #64748B;
}

.empty-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #F1F5F9;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94A3B8;
}

.upload-btn,
.start-btn,
.edit-btn,
.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  transition: all 150ms;
}

.upload-btn {
  background: #2563EB;
  color: #FFFFFF;
}

.upload-btn:hover {
  background: #1D4ED8;
}

.start-btn {
  background: #F1F5F9;
  color: #475569;
}

.start-btn:hover {
  background: #E2E8F0;
}

/* 学情档案 */
.profile-card {
  background: #FFFFFF;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
  overflow: hidden;
}

.profile-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #F1F5F9;
}

.profile-card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
}

.edit-btn {
  padding: 6px 12px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563EB;
  font-size: 13px;
}

.edit-btn:hover {
  background: rgba(37, 99, 235, 0.2);
}

.profile-empty {
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
  margin: 0 !important;
}

.empty-desc {
  font-size: 13px;
  color: #64748B;
  margin: 0 !important;
}

.profile-info-list {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 13px;
  color: #64748B;
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: #1E293B;
}

.pain-points {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pain-tag {
  padding: 4px 10px;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 12px;
  font-size: 12px;
  color: #D97706;
}

/* 知识漏洞 */
.gap-status-tabs {
  display: flex;
  gap: 4px;
  background: #FFFFFF;
  padding: 6px;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
}

.gap-status-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #64748B;
  transition: all 150ms;
}

.gap-status-tab--active {
  background: #F1F5F9;
  color: #1E293B;
}

.gap-count {
  background: #E2E8F0;
  color: #475569;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.gap-status-tab--active .gap-count {
  background: #CBD5E1;
  color: #1E293B;
}

.gaps-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gap-card {
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  overflow: hidden;
}

.gap-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #F8FAFC;
  border-bottom: 1px solid #E2E8F0;
}

.gap-kp-name {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.gap-dimension-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.gap-dimension-tag.dim-deep {
  background: rgba(59, 130, 246, 0.1);
  color: #3B82F6;
}

.gap-dimension-tag.dim-complete {
  background: rgba(16, 185, 129, 0.1);
  color: #10B981;
}

.gap-dimension-tag.dim-logic {
  background: rgba(139, 92, 246, 0.1);
  color: #8B5CF6;
}

.gap-dimension-tag.dim-struct {
  background: rgba(245, 158, 11, 0.1);
  color: #F59E0B;
}

.gap-dimension-tag.dim-proof {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
}

.gap-body {
  padding: 16px;
}

.gap-description {
  margin: 0 0 12px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.gap-meta {
  display: flex;
  align-items: center;
  gap: 16px;
}

.gap-score {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-current {
  font-size: 18px;
  font-weight: 700;
  color: #2563EB;
}

.score-total {
  font-size: 12px;
  color: #94A3B8;
}

.gap-severity {
  display: flex;
  gap: 2px;
}

.star {
  color: #CBD5E1;
  font-size: 14px;
}

.star--active {
  color: #F59E0B;
}

.gap-date {
  margin-left: auto;
  font-size: 12px;
  color: #94A3B8;
}

.gap-actions {
  display: flex;
  padding: 12px 16px;
  border-top: 1px solid #F1F5F9;
  gap: 8px;
}

.action-btn {
  flex: 1;
  justify-content: center;
  padding: 8px 12px;
  font-size: 13px;
}

.action-btn--review {
  background: rgba(245, 158, 11, 0.1);
  color: #D97706;
}

.action-btn--review:hover {
  background: rgba(245, 158, 11, 0.2);
}

.action-btn--master {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.action-btn--master:hover {
  background: rgba(16, 185, 129, 0.2);
}

.action-btn--reopen {
  background: #F1F5F9;
  color: #64748B;
}

.action-btn--reopen:hover {
  background: #E2E8F0;
}

/* 历史报告 */
.reports-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-card {
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  padding: 16px;
  cursor: pointer;
  transition: all 150ms;
}

.report-card:hover {
  border-color: #2563EB;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.1);
}

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.report-kp-name {
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
}

.report-score-badge {
  display: flex;
  align-items: baseline;
  gap: 2px;
  padding: 4px 12px;
  background: rgba(37, 99, 235, 0.1);
  border-radius: 8px;
}

.report-score-badge .score-value {
  font-size: 20px;
  font-weight: 700;
  color: #2563EB;
}

.report-score-badge .score-max {
  font-size: 12px;
  color: #64748B;
}

.report-dimensions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dim-name {
  width: 80px;
  font-size: 12px;
  color: #64748B;
}

.dim-progress {
  flex: 1;
  height: 6px;
  background: #E2E8F0;
  border-radius: 3px;
  overflow: hidden;
}

.dim-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 300ms ease;
}

.dim-fill.score-high {
  background: #10B981;
}

.dim-fill.score-mid {
  background: #F59E0B;
}

.dim-fill.score-low {
  background: #EF4444;
}

.dim-score {
  width: 24px;
  text-align: right;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.report-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #F1F5F9;
  font-size: 12px;
  color: #94A3B8;
}

/* 教材列表 */
.materials-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.material-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  cursor: pointer;
  transition: all 150ms;
}

.material-card:hover {
  border-color: #2563EB;
  background: rgba(37, 99, 235, 0.02);
}

.material-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563EB;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
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

.material-meta {
  font-size: 13px;
  color: #64748B;
}

.material-meta span {
  margin-right: 4px;
}

.material-date {
  font-size: 12px;
  color: #94A3B8;
  flex-shrink: 0;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 历史会话 */
.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.session-card {
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  padding: 16px;
}

.session-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.session-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(139, 92, 246, 0.1);
  color: #8B5CF6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-kp-name {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
  margin-bottom: 4px;
}

.session-meta {
  font-size: 12px;
  color: #64748B;
  display: flex;
  align-items: center;
  gap: 4px;
}

.session-dot {
  color: #CBD5E1;
}

.session-actions {
  display: flex;
  gap: 8px;
}

.session-actions .action-btn {
  flex: 1;
  justify-content: center;
  padding: 8px 12px;
  font-size: 13px;
}

.action-btn--view {
  background: #F1F5F9;
  color: #475569;
}

.action-btn--view:hover {
  background: #E2E8F0;
}

.action-btn--continue {
  background: rgba(139, 92, 246, 0.1);
  color: #8B5CF6;
}

.action-btn--continue:hover {
  background: rgba(139, 92, 246, 0.2);
}

/* 会话详情弹窗 */
.session-drawer-overlay {
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

.session-drawer {
  background: #FFFFFF;
  border-radius: 16px;
  width: 100%;
  max-width: 500px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.session-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #E2E8F0;
}

.session-drawer-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1E293B;
}

.session-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.session-drawer-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #E2E8F0;
  background: #F8FAFC;
}

.session-drawer-footer .btn {
  flex: 1;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
}

.session-detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-section {
  background: #F8FAFC;
  border-radius: 12px;
  padding: 16px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #E2E8F0;
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-label {
  font-size: 13px;
  color: #64748B;
}

.detail-value {
  font-size: 14px;
  font-weight: 500;
  color: #1E293B;
}

.detail-section-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}

.chat-history {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-message {
  display: flex;
  gap: 8px;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.chat-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.chat-message.assistant .chat-avatar {
  background: #DBEAFE;
  color: #2563EB;
}

.chat-message.user .chat-avatar {
  background: #EDE9FE;
  color: #8B5CF6;
}

.chat-bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.chat-message.assistant .chat-bubble {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  color: #1E293B;
}

.chat-message.user .chat-bubble {
  background: #2563EB;
  color: #FFFFFF;
}

.empty-chat {
  text-align: center;
  padding: 20px;
  color: #94A3B8;
}

.empty-chat p {
  margin: 0;
}

/* Drawer buttons */
.session-drawer-footer .btn-primary {
  background: #2563EB;
  color: #FFFFFF;
}

.session-drawer-footer .btn-primary:hover {
  background: #1D4ED8;
}

.session-drawer-footer .btn-secondary {
  background: #F1F5F9;
  color: #475569;
}

.session-drawer-footer .btn-secondary:hover {
  background: #E2E8F0;
}
</style>