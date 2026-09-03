<script setup>
import { ref, onMounted, computed, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore } from '@/stores/chatStore'
import { getKnowledgeTree, getUserProfile, getGaps, getGapsStats, updateGapStatus, getReports, getReportDetail, getSessionList, getSessionDetail, fetchSubjects, getReviewDueGaps, getUserStats, startReview } from '@/api/feynman'
import ProfileSetupModal from '@/components/ProfileSetupModal.vue'
import ReportDrawer from '@/components/ReportDrawer.vue'

const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()

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
const expandedKps = ref(new Set())
const reviewDueGaps = ref([])
const showReviewDue = ref(false)
const loadingReviewDue = ref(false)

// 复习入口加载态：避免重复点击
const reviewStarting = ref(false)
const reviewStartingKpId = ref('')

// 标记是否从对话页返回（返回后需要刷新漏洞/统计）
const needRefreshOnReturn = ref(false)

// 学情统计
const userStats = ref(null)
const loadingUserStats = ref(false)

function toggleKp(kpId) {
  const next = new Set(expandedKps.value)
  if (next.has(kpId)) {
    next.delete(kpId)
  } else {
    next.add(kpId)
  }
  expandedKps.value = next
}

/**
 * 知识漏洞列表：开始复习 / 手动标记已掌握 / 重新打开
 * 第八周：开始复习统一调用 POST /reviews/start，不再直接 PATCH reviewing
 * - 有 open/reviewing 维度 → startReview + 进入对话
 * - 全部 resolved → 手动重新打开（PATCH open）
 * - 复习中 → 手动标记已掌握（PATCH resolved）
 */
async function startReviewKp(group) {
  // 有未解决漏洞：调用 startReview 进入复习对话
  if (group.dimensions.some(d => d.status === 'open' || d.status === 'reviewing')) {
    if (reviewStarting.value) return
    reviewStarting.value = true
    reviewStartingKpId.value = group.kp_id
    try {
      const reviewData = await startReview(group.kp_id, 'gap')
      // 设置 chatStore 复习上下文（reviewId/sessionId/targetGaps 等）
      chatStore.clearReviewContext()
      chatStore.clearKnowledgeContext()
      chatStore.setKnowledgePoint(group.kp_id, group.kp_name)
      chatStore.startReviewContext(reviewData)
      // 标记返回后需要刷新
      needRefreshOnReturn.value = true
      router.push('/home')
    } catch (e) {
      const msg = e.status === 409
        ? '当前知识点暂无未解决漏洞，可能已全部掌握'
        : '开始复习失败: ' + e.message
      alert(msg)
    } finally {
      reviewStarting.value = false
      reviewStartingKpId.value = ''
    }
    return
  }
  // 全部已掌握：手动重新打开
  if (group.dimensions.every(d => d.status === 'resolved')) {
    try {
      for (const dim of group.dimensions) {
        await updateGapStatus(dim.gap_id, 'open')
      }
      await Promise.all([loadGaps(), loadReviewDueGaps(false)])
    } catch (e) {
      alert('重新打开失败: ' + e.message)
    }
    return
  }
  // 复习中：手动标记已掌握
  try {
    for (const dim of group.dimensions) {
      if (dim.status !== 'resolved') await updateGapStatus(dim.gap_id, 'resolved')
    }
    await loadGaps()
  } catch (e) {
    alert('标记已掌握失败: ' + e.message)
  }
}

/**
 * 今日待复习：开始或继续复习
 * 第八周：统一调用 POST /reviews/start
 * - action='start' → 新建复习记录
 * - action='continue' → 返回已有 active 记录（resumed=true）
 * 进入对话后保留知识点信息和本次复习目标
 */
async function startDueReview(gap) {
  if (reviewStarting.value) return
  reviewStarting.value = true
  reviewStartingKpId.value = gap.kp_id
  try {
    const reviewData = await startReview(gap.kp_id, 'due')
    chatStore.clearReviewContext()
    chatStore.clearKnowledgeContext()
    chatStore.setKnowledgePoint(gap.kp_id, gap.kp_name)
    chatStore.startReviewContext(reviewData)
    needRefreshOnReturn.value = true
    router.push('/home')
  } catch (e) {
    const msg = e.status === 409
      ? '当前知识点暂无未解决漏洞，可能已全部掌握'
      : '开始复习失败: ' + e.message
    alert(msg)
  } finally {
    reviewStarting.value = false
    reviewStartingKpId.value = ''
  }
}

// 按 kp_id 分组，每张卡片代表一个 KP
const groupedGaps = computed(() => {
  const grouped = {}
  for (const gap of gaps.value) {
    if (!grouped[gap.kp_id]) {
      grouped[gap.kp_id] = {
        kp_id: gap.kp_id,
        kp_name: gap.kp_name,
        material_name: gap.material_name,
        dimensions: [],
        status: 'open',
        created_at: gap.created_at
      }
    }
    grouped[gap.kp_id].dimensions.push({
      gap_id: gap.gap_id,
      dimension: gap.dimension,
      score: gap.score,
      severity: gap.severity,
      gap_description: gap.gap_description,
      status: gap.status,
      created_at: gap.created_at
    })
    if (gap.status === 'open' && grouped[gap.kp_id].status !== 'open') {
      grouped[gap.kp_id].status = 'open'
    }
    if (grouped[gap.kp_id].created_at < gap.created_at) {
      grouped[gap.kp_id].created_at = gap.created_at
    }
  }
  return Object.values(grouped)
})

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

const trendMaxScore = computed(() => {
  if (!userStats.value?.recent_trend?.length) return 40
  return Math.max(...userStats.value.recent_trend.map(t => t.total_score), 1)
})

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

async function loadReviewDueGaps(openList = true) {
  if (!isLoggedIn.value) return
  loadingReviewDue.value = true
  try {
    const data = await getReviewDueGaps()
    reviewDueGaps.value = data.items || []
    if (openList) showReviewDue.value = true
  } catch (e) {
    reviewDueGaps.value = []
  } finally {
    loadingReviewDue.value = false
  }
}

async function loadUserStats() {
  if (!isLoggedIn.value) return
  loadingUserStats.value = true
  try {
    const data = await getUserStats()
    userStats.value = data
  } catch (e) {
    userStats.value = null
  } finally {
    loadingUserStats.value = false
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
    const subjects = await fetchSubjects()
    const allMaterials = []
    for (const subject of subjects) {
      try {
        const tree = await getKnowledgeTree(subject)
        const mapped = tree.map(m => ({
          id: m.material_id,
          name: (m.title || '未命名教材') + '.pdf',
          subject: subject,
          chapters: m.chapters?.length || 0,
          kps: m.chapters?.reduce((sum, ch) => sum + (ch.knowledge_points?.length || 0), 0) || 0,
          createdAt: m.created_at || ''
        }))
        allMaterials.push(...mapped)
      } catch (e) {
        // 单个学科加载失败不阻塞其他
      }
    }
    materials.value = allMaterials
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
    loadReviewDueGaps(false)
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
  // 第八周：从复习对话返回时，自动切到知识漏洞页签并刷新数据
  const route = router.currentRoute.value
  const fromReview = route.query.from === 'review'
  if (fromReview) {
    activeTab.value = 'gaps'
    // 清除 query，避免刷新后重复触发
    router.replace({ path: '/profile' })
  }
  // 加载学情统计数据
  loadUserStats()
  // 根据当前tab加载数据
  if (activeTab.value === 'profile') {
    loadUserProfile()
  } else if (activeTab.value === 'gaps') {
    loadGaps()
    loadReviewDueGaps(false)
  } else if (activeTab.value === 'sessions') {
    loadSessions()
  } else if (activeTab.value === 'reports') {
    loadReports()
  } else if (activeTab.value === 'materials') {
    loadMaterials()
  }
})

// 第八周：返回个人中心时刷新所有相关数据
// 配合 ChatView 的 router.push('/profile?from=review') 使用
onActivated(() => {
  if (needRefreshOnReturn.value) {
    needRefreshOnReturn.value = false
    loadUserStats()
    if (activeTab.value === 'gaps') {
      loadGaps()
      loadReviewDueGaps(false)
    } else if (activeTab.value === 'reports') {
      loadReports()
    }
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
      <div class="profile-layout">
        <aside class="profile-sidebar">
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
        </aside>

        <section class="profile-content">
      <!-- 学情档案 Tab -->
      <div v-if="activeTab === 'profile'" class="tab-content">
        <!-- 学情统计概览 -->
        <div v-if="isLoggedIn" class="stats-card">
          <div v-if="loadingUserStats" class="loading-state">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
              <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
            </svg>
            <p>加载中...</p>
          </div>

          <div v-else-if="!userStats || userStats.total_kps_learned === 0" class="stats-empty">
            <div class="empty-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <p class="empty-title">尚未开始学习</p>
            <p class="empty-desc">去选择一个知识点开始吧</p>
            <button class="start-btn" @click="router.push('/select')">
              开始学习
            </button>
          </div>

          <div v-else class="stats-content">
            <div class="stats-grid">
              <div class="stat-item">
                <span class="stat-value">{{ userStats.total_kps_learned }}</span>
                <span class="stat-label">已学习知识点</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ userStats.total_sessions }}</span>
                <span class="stat-label">总对话次数</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ userStats.avg_total_score }}</span>
                <span class="stat-label">平均得分</span>
              </div>
            </div>

            <div class="dimension-avg-section">
              <span class="section-title">四维度平均分</span>
              <div class="dimension-bars">
                <div v-for="(score, dim) in userStats.dimension_avg" :key="dim" class="dim-bar-row">
                  <span class="dim-label">{{ dim }}</span>
                  <div class="dim-progress-mini">
                    <div
                      class="dim-fill-mini"
                      :style="{ width: (score / 10 * 100) + '%' }"
                      :class="{ 'dim-weakest': dim === userStats.weakest_dimension }"
                    ></div>
                  </div>
                  <span class="dim-score-mini" :class="{ 'score-weakest': dim === userStats.weakest_dimension }">
                    {{ score }}
                  </span>
                  <span v-if="dim === userStats.weakest_dimension" class="weakest-badge">最薄弱</span>
                </div>
              </div>
            </div>

            <div v-if="userStats.recent_trend && userStats.recent_trend.length > 0" class="trend-section">
              <span class="section-title">总分趋势</span>
              <div class="trend-chart">
                <div v-for="item in userStats.recent_trend" :key="item.date" class="trend-bar-col">
                  <div class="trend-bar-wrap">
                    <div
                      class="trend-bar"
                      :style="{ height: (item.total_score / trendMaxScore * 100) + '%' }"
                    >
                      <span class="trend-bar-score">{{ item.total_score }}</span>
                    </div>
                  </div>
                  <span class="trend-bar-date">{{ item.date.slice(5) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

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
        <!-- 今日待复习按钮 -->
        <button v-if="!showReviewDue" class="review-due-btn" @click="loadReviewDueGaps">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          <span>🔔 今日待复习</span>
          <span v-if="reviewDueGaps.length > 0" class="review-badge">{{ reviewDueGaps.length }}</span>
        </button>

        <!-- 今日待复习列表 -->
        <div v-if="showReviewDue" class="review-due-list">
          <div class="review-due-header">
            <span class="review-due-title">🔔 今日待复习</span>
            <button class="close-review-btn" @click="showReviewDue = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div v-if="loadingReviewDue" class="loading-state">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
              <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
            </svg>
            <p>加载中...</p>
          </div>

          <div v-else-if="reviewDueGaps.length === 0" class="empty-state">
            <div class="empty-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <polyline points="22 11 18 11 15 21 9 3 6 11 2 11" />
              </svg>
            </div>
            <p>今日暂无待复习的漏洞</p>
          </div>

          <div v-else class="review-gaps-grid">
            <div v-for="gap in reviewDueGaps" :key="gap.gap_id" class="review-gap-card">
              <div class="review-gap-header">
                <span class="review-gap-kp">{{ gap.kp_name }}</span>
                <span class="review-gap-dim" :class="getDimensionClass(gap.dimension)">{{ gap.dimension }}</span>
              </div>
              <div class="review-gap-score">
                <span class="review-score-value">{{ gap.score }}</span>
                <span class="review-score-max">/ 10</span>
              </div>
              <p class="review-gap-desc">{{ gap.gap_description }}</p>
              <button
                class="review-action-btn"
                :disabled="reviewStarting && reviewStartingKpId === gap.kp_id"
                @click="startDueReview(gap)"
              >
                <svg
                  v-if="reviewStarting && reviewStartingKpId === gap.kp_id"
                  width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner"
                >
                  <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
                </svg>
                <span v-if="reviewStarting && reviewStartingKpId === gap.kp_id">进入复习中...</span>
                <span v-else-if="gap.action === 'continue'">继续复习</span>
                <span v-else>开始复习</span>
              </button>
            </div>
          </div>
        </div>

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
        <div v-else-if="groupedGaps.length === 0" class="empty-state">
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

        <!-- 漏洞列表（按 KP 分组，折叠展开） -->
        <div v-else class="gaps-list">
          <div
            v-for="group in groupedGaps"
            :key="group.kp_id"
            class="gap-card"
            :class="{ 'gap-card--expanded': expandedKps.has(group.kp_id) }"
          >
            <div class="gap-header" @click="toggleKp(group.kp_id)">
              <div class="gap-kp-info">
                <span class="gap-kp-name">{{ group.kp_name }}</span>
                <span class="gap-material-name" v-if="group.material_name">{{ group.material_name }}</span>
              </div>
              <div class="gap-header-right">
                <span class="gap-dim-count">{{ group.dimensions.length }} 个薄弱维度</span>
                <span class="gap-chevron" :class="{ 'gap-chevron--open': expandedKps.has(group.kp_id) }">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </span>
              </div>
            </div>

            <div v-if="expandedKps.has(group.kp_id)" class="gap-dimensions-grid">
              <div
                v-for="dim in group.dimensions"
                :key="dim.gap_id"
                class="gap-dim-row"
              >
                <div class="dim-row-header">
                  <span class="dim-tag" :class="getDimensionClass(dim.dimension)">{{ dim.dimension }}</span>
                  <span class="dim-score-text">{{ dim.score }}<small>/10</small></span>
                </div>
                <div class="dim-progress">
                  <div
                    class="dim-fill"
                    :style="{ width: (dim.score / 10 * 100) + '%' }"
                    :class="getScoreClass(dim.score)"
                  ></div>
                </div>
                <p class="dim-desc" v-if="dim.gap_description">{{ dim.gap_description }}</p>
              </div>

              <div class="gap-card-actions">
                <button
                  v-if="group.dimensions.some(d => d.status === 'open' || d.status === 'reviewing')"
                  class="action-btn action-btn--review"
                  :disabled="reviewStarting && reviewStartingKpId === group.kp_id"
                  @click.stop="startReviewKp(group)"
                >
                  <svg
                    v-if="reviewStarting && reviewStartingKpId === group.kp_id"
                    width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner"
                  >
                    <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
                  </svg>
                  <span v-if="reviewStarting && reviewStartingKpId === group.kp_id">进入复习中...</span>
                  <span v-else>开始复习</span>
                </button>
                <button
                  v-if="group.dimensions.every(d => d.status === 'resolved')"
                  class="action-btn action-btn--reopen"
                  @click.stop="startReviewKp(group)"
                >
                  重新打开
                </button>
                <button
                  v-if="!group.dimensions.some(d => d.status === 'open') && !group.dimensions.every(d => d.status === 'resolved')"
                  class="action-btn action-btn--master"
                  @click.stop="startReviewKp(group)"
                >
                  全部标记已掌握
                </button>
              </div>
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
        </section>
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
  padding: 24px 24px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.profile-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.profile-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 76px;
  align-self: flex-start;
  min-height: calc(100vh - 76px);
  overflow-y: auto;
}

.profile-content {
  flex: 1;
  min-width: 0;
  max-width: 920px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 用户卡片 */
.user-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  background: #FFFFFF;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
  text-align: center;
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
  text-align: center;
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

/* 学情统计卡片 */
.stats-card {
  background: #FFFFFF;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
  overflow: hidden;
}

.stats-empty {
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.stats-content {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #2563EB;
}

.stat-label {
  font-size: 12px;
  color: #64748B;
}

.dimension-avg-section {
  background: #F8FAFC;
  border-radius: 12px;
  padding: 16px;
}

.section-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
}

.dimension-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dim-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dim-label {
  width: 80px;
  font-size: 13px;
  color: #475569;
}

.dim-progress-mini {
  flex: 1;
  height: 6px;
  background: #E2E8F0;
  border-radius: 3px;
  overflow: hidden;
}

.dim-fill-mini {
  height: 100%;
  background: #2563EB;
  border-radius: 3px;
  transition: width 300ms ease;
}

.dim-fill-mini.dim-weakest {
  background: #EF4444;
}

.dim-score-mini {
  width: 24px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.dim-score-mini.score-weakest {
  color: #EF4444;
}

.weakest-badge {
  padding: 2px 8px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  color: #EF4444;
}

/* 总分趋势图 */
.trend-section {
  background: #F8FAFC;
  border-radius: 12px;
  padding: 16px;
}

.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  height: 100px;
}

.trend-bar-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.trend-bar-wrap {
  width: 100%;
  height: 70px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.trend-bar {
  width: 60%;
  min-height: 4px;
  background: linear-gradient(180deg, #3B82F6 0%, #2563EB 100%);
  border-radius: 4px 4px 0 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 4px;
  transition: height 400ms ease;
}

.trend-bar-score {
  font-size: 11px;
  font-weight: 600;
  color: #FFFFFF;
}

.trend-bar-date {
  font-size: 11px;
  color: #6B7280;
}

/* 今日待复习按钮和列表 */
.review-due-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 12px 16px;
  background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
  border: 1px solid #F59E0B;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #92400E;
  cursor: pointer;
  transition: all 150ms;
  margin-bottom: 12px;
}

.review-due-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.2);
}

.review-badge {
  margin-left: auto;
  padding: 2px 10px;
  background: #F59E0B;
  color: #FFFFFF;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.review-due-list {
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid #F59E0B;
  overflow: hidden;
  margin-bottom: 12px;
}

.review-due-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
  border-bottom: 1px solid #FCD34D;
}

.review-due-title {
  font-size: 14px;
  font-weight: 600;
  color: #92400E;
}

.close-review-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.5);
  border: none;
  border-radius: 50%;
  color: #92400E;
  cursor: pointer;
  transition: all 150ms;
}

.close-review-btn:hover {
  background: rgba(255, 255, 255, 0.8);
}

.review-gaps-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.review-gap-card {
  padding: 16px;
  background: #F8FAFC;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
}

.review-gap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.review-gap-kp {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.review-gap-dim {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.review-gap-dim.dim-deep {
  background: rgba(59, 130, 246, 0.1);
  color: #3B82F6;
}
.review-gap-dim.dim-complete {
  background: rgba(16, 185, 129, 0.1);
  color: #10B981;
}
.review-gap-dim.dim-logic {
  background: rgba(139, 92, 246, 0.1);
  color: #8B5CF6;
}
.review-gap-dim.dim-struct {
  background: rgba(245, 158, 11, 0.1);
  color: #F59E0B;
}
.review-gap-dim.dim-proof {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
}
.review-gap-dim.dim-default {
  background: #F1F5F9;
  color: #64748B;
}

.review-gap-score {
  margin-bottom: 8px;
}

.review-score-value {
  font-size: 18px;
  font-weight: 700;
  color: #EF4444;
}

.review-score-max {
  font-size: 12px;
  color: #94A3B8;
}

.review-gap-desc {
  font-size: 13px;
  color: #64748B;
  line-height: 1.5;
  margin: 0 0 12px;
}

.review-action-btn {
  width: 100%;
  padding: 8px 16px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid #F59E0B;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #D97706;
  cursor: pointer;
  transition: all 150ms;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.review-action-btn:hover:not(:disabled) {
  background: rgba(245, 158, 11, 0.2);
}

.review-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.review-action-btn .spinner {
  animation: spin 1s linear infinite;
}

.gap-card-actions .action-btn .spinner {
  animation: spin 1s linear infinite;
}

/* Tab 容器 */
.tabs-container {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #FFFFFF;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
}

.tab-btn {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #64748B;
  text-align: left;
  border-left: 3px solid transparent;
  transition: all 150ms;
}

.tab-btn--active {
  background: rgba(37, 99, 235, 0.1);
  color: #2563EB;
  border-left: 3px solid #2563EB;
}

.tab-btn--active svg {
  color: #2563EB;
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

.gap-card--expanded {
  border-color: #2563EB;
}

.gap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #F8FAFC;
  cursor: pointer;
  user-select: none;
  transition: background 150ms;
}

.gap-header:hover {
  background: #F1F5F9;
}

.gap-kp-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.gap-kp-name {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.gap-material-name {
  font-size: 12px;
  color: #64748B;
}

.gap-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.gap-dim-count {
  font-size: 12px;
  color: #64748B;
}

.gap-chevron {
  display: flex;
  align-items: center;
  color: #94A3B8;
  transition: transform 200ms ease;
}

.gap-chevron--open {
  transform: rotate(180deg);
}

.gap-dimensions-grid {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.gap-dim-row {
  padding-bottom: 12px;
  border-bottom: 1px solid #F1F5F9;
}

.gap-dim-row:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.dim-row-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.dim-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.dim-tag.dim-deep {
  background: rgba(59, 130, 246, 0.1);
  color: #3B82F6;
}
.dim-tag.dim-complete {
  background: rgba(16, 185, 129, 0.1);
  color: #10B981;
}
.dim-tag.dim-logic {
  background: rgba(139, 92, 246, 0.1);
  color: #8B5CF6;
}
.dim-tag.dim-struct {
  background: rgba(245, 158, 11, 0.1);
  color: #F59E0B;
}
.dim-tag.dim-proof {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
}
.dim-tag.dim-default {
  background: #F1F5F9;
  color: #64748B;
}

.dim-score-text {
  font-size: 15px;
  font-weight: 700;
  color: #1E293B;
}
.dim-score-text small {
  font-size: 11px;
  color: #94A3B8;
  font-weight: 400;
}

.dim-progress {
  height: 5px;
  background: #E2E8F0;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}
.dim-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 300ms ease;
}
.dim-fill.score-high { background: #10B981; }
.dim-fill.score-mid  { background: #F59E0B; }
.dim-fill.score-low  { background: #EF4444; }

.dim-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748B;
  line-height: 1.4;
}

.gap-card-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #E2E8F0;
}
.gap-card-actions .action-btn {
  flex: 1;
  justify-content: center;
  padding: 8px 16px;
  font-size: 13px;
}

.action-btn {
  flex: none;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  transition: all 150ms;
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

/* 响应式：小屏幕回退为上下布局 */
@media (max-width: 767px) {
  .profile-layout {
    flex-direction: column;
  }

  .profile-sidebar {
    width: 100%;
  }
}
</style>
