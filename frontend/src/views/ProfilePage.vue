<script setup>
import { ref, onMounted, computed, onActivated, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore } from '@/stores/chatStore'
import { getKnowledgeTree, getUserProfile, getGaps, getGapsStats, updateGapStatus, getReports, getReportDetail, getSessionList, getSessionDetail, fetchSubjects, getReviewDueGaps, getUserStats, startReview, addReportToReviewList } from '@/api/feynman'
import ProfileSetupModal from '@/components/ProfileSetupModal.vue'
import ReportDrawer from '@/components/DetailedReportDrawer.vue'
import FavoriteCardsPanel from '@/components/FavoriteCardsPanel.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()

const activeTab = ref('profile')
const pageTitle = computed(() => ({
  profile: '个人主页',
  gaps: '复习计划',
  sessions: '教材讲解记录',
  reports: '学习历史',
  materials: '我的教材',
  favorites: '知识收藏'
}[activeTab.value] || '个人主页'))
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
const reviewDueGaps = ref([])
const showReviewDue = ref(false)
const loadingReviewDue = ref(false)

// 复习入口加载态：避免重复点击
const reviewStarting = ref(false)
const reviewStartingKpId = ref('')

// 标记是否从对话页返回（返回后需要刷新漏洞/统计）
const needRefreshOnReturn = ref(false)

// 轻量 toast 提示（用于「继续上次复习」等短暂通知）
const toastText = ref('')
const toastVisible = ref(false)
let toastTimer = null
function showToast(msg, duration = 2200) {
  toastText.value = msg
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, duration)
}

// 学情统计
const userStats = ref(null)
const loadingUserStats = ref(false)

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
      // 恢复已有复习记录时给出提示
      if (reviewData.resumed) {
        showToast('继续上次复习')
      }
      // 设置 chatStore 复习上下文（reviewId/sessionId/targetGaps 等）
      chatStore.clearReviewContext()
      chatStore.clearKnowledgeContext()
      chatStore.setKnowledgePoint(group.kp_id, group.kp_name)
      chatStore.startReviewContext(reviewData)
      // 标记返回后需要刷新
      needRefreshOnReturn.value = true
      router.push('/study')
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
    if (reviewData.resumed) {
      showToast('继续上次复习')
    }
    chatStore.clearReviewContext()
    chatStore.clearKnowledgeContext()
    chatStore.setKnowledgePoint(gap.kp_id, gap.kp_name)
    chatStore.startReviewContext(reviewData)
    needRefreshOnReturn.value = true
    router.push('/study')
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
      created_at: gap.created_at,
      review_count: gap.review_count,
      last_reviewed_at: gap.last_reviewed_at,
      next_review_at: gap.next_review_at
    })
    const currentFocus = grouped[gap.kp_id].focus
    if (!currentFocus || Number(gap.score) < Number(currentFocus.score)) {
      grouped[gap.kp_id].focus = {
        dimension: gap.dimension,
        score: gap.score
      }
    }
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
const reportReviewAdding = ref(false)
const reportOpeningKpId = ref('')

// 学习历史：历史报告 + 历史会话合并后的时间轴卡片
const historyCards = ref([])
const loadingHistory = ref(false)

// 我的教材
const materials = ref([])
const loadingMaterials = ref(false)

// 历史会话
const sessions = ref([])
const loadingSessions = ref(false)
const showSessionDetail = ref(false)
const selectedSession = ref(null)
const sessionDetailLoading = ref(false)

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
    path: '/study',
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

/**
 * 学习历史：合并历史报告与历史会话（仅组合现有两个接口的数据，不新增接口）
 * 配对规则（sessions 无 kp_id）：同一 kp_name 下按 created_at 时间差最近配对，
 * 每个会话最多配给一个报告；未配对的会话仍单独生成卡片。
 */
async function loadHistory() {
  if (!isLoggedIn.value) return
  loadingHistory.value = true
  try {
    const [sessionListData, reportsData] = await Promise.all([
      getSessionList(),
      getReports()
    ])
    const sessionList = sessionListData || []
    const reportList = reportsData.items || []
    reports.value = reportList

    const candidates = []
    reportList.forEach((report, ri) => {
      sessionList.forEach((session, si) => {
        if (session.kp_name !== report.kp_name) return
        const delta = Math.abs(new Date(session.created_at) - new Date(report.created_at))
        candidates.push({ ri, si, delta })
      })
    })
    candidates.sort((a, b) => a.delta - b.delta)

    const reportSession = new Map()
    const usedSessions = new Set()
    for (const candidate of candidates) {
      if (reportSession.has(candidate.ri) || usedSessions.has(candidate.si)) continue
      reportSession.set(candidate.ri, candidate.si)
      usedSessions.add(candidate.si)
    }

    const cards = reportList.map((report, ri) => {
      const sessionIndex = reportSession.get(ri)
      const session = sessionIndex !== undefined ? sessionList[sessionIndex] : null
      return {
        key: `report-${report.report_id}`,
        kp_name: report.kp_name,
        material_name: report.material_name,
        created_at: report.created_at,
        total_score: report.total_score,
        dimensions: report.dimensions || [],
        report,
        session
      }
    })

    sessionList.forEach((session, si) => {
      if (usedSessions.has(si)) return
      cards.push({
        key: `session-${session.session_id}`,
        kp_name: session.kp_name,
        material_name: session.material_title,
        created_at: session.created_at,
        total_score: null,
        dimensions: [],
        report: null,
        session
      })
    })

    cards.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    historyCards.value = cards
  } catch (e) {
    historyCards.value = []
  } finally {
    loadingHistory.value = false
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

async function viewLatestReportForKp(group) {
  if (reportOpeningKpId.value) return
  reportOpeningKpId.value = group.kp_id
  try {
    const data = await getReports({ kpId: group.kp_id, pageSize: 1 })
    const report = data.items?.[0]
    if (!report) {
      showToast('这个知识点暂无可查看的学习报告')
      return
    }
    await viewReportDetail(report)
  } catch (error) {
    showToast(error.message || '学习报告加载失败')
  } finally {
    reportOpeningKpId.value = ''
  }
}

async function addSelectedReportToReviewList() {
  if (!selectedReport.value?.report_id || reportReviewAdding.value) return
  reportReviewAdding.value = true
  try {
    await addReportToReviewList(selectedReport.value.report_id)
    selectedReport.value.review_list_added = true
    selectedReport.value.review_list_source = null
    await loadGaps()
  } catch (error) {
    showToast(error.message || '加入复习列表失败')
  } finally {
    reportReviewAdding.value = false
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
    loadHistory()
  } else if (key === 'materials') {
    loadMaterials()
  }
}

watch(() => route.query.tab, tab => {
  if (['profile', 'gaps', 'sessions', 'reports', 'materials', 'favorites'].includes(tab) && tab !== activeTab.value) {
    handleTabChange(tab)
  }
})

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
  } else if (['profile', 'gaps', 'sessions', 'reports', 'materials', 'favorites'].includes(route.query.tab)) {
    activeTab.value = route.query.tab
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
    loadHistory()
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
      loadHistory()
    }
  }
})
</script>

<template>
  <div class="profile-page">
    <header v-if="activeTab !== 'reports'" class="profile-header">
      <h1 class="page-title">{{ pageTitle }}</h1>
    </header>

    <main class="profile-main">
      <div class="profile-layout">
        <section class="profile-content">
      <!-- 个人主页保留身份和学情；功能入口统一交给应用左侧导航。 -->
      <div v-if="activeTab === 'profile'" class="user-card">
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
        <div v-else class="profile-quick-actions">
          <button class="record-link record-link--favorite" type="button" @click="router.push('/profile?tab=favorites')">
            ★ 知识收藏
          </button>
          <button class="record-link" type="button" @click="router.push('/profile?tab=sessions')">
            查看教材讲解记录
          </button>
        </div>
      </div>
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

      <div v-if="activeTab === 'favorites'" class="tab-content">
        <FavoriteCardsPanel v-if="isLoggedIn" />
        <div v-else class="empty-state">
          <div class="empty-icon">☆</div>
          <p>登录后建立你自己的知识收藏夹</p>
          <button class="upload-btn" @click="router.push('/login')">去登录</button>
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
              <span v-if="gap.dimension_count > 1" class="review-gap-count">共 {{ gap.dimension_count }} 个待复习维度，当前展示最低分重点</span>
              <div class="review-gap-score">
                <span class="review-score-value">{{ gap.score }}</span>
                <span class="review-score-max">/ 10</span>
              </div>
              <p class="review-gap-desc">{{ gap.gap_description }}</p>
              <div class="review-gap-meta">
                <span
                  v-if="formatNextReview(gap.next_review_at)"
                  class="review-time-tag"
                  :class="{ 'review-time--overdue': isOverdue(gap.next_review_at) }"
                >
                  {{ formatNextReview(gap.next_review_at) }}
                </span>
                <span
                  v-if="gap.status === 'reviewing' && formatLastReviewed(gap.last_reviewed_at)"
                  class="last-review-tag"
                >
                  {{ formatLastReviewed(gap.last_reviewed_at) }}
                </span>
              </div>
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

        <!-- 复习知识点列表：每张卡片代表一个 KP，点击查看最近学习报告。 -->
        <div v-else class="gaps-list">
          <article
            v-for="group in groupedGaps"
            :key="group.kp_id"
            class="gap-card"
            role="button"
            tabindex="0"
            @click="viewLatestReportForKp(group)"
            @keydown.enter="viewLatestReportForKp(group)"
          >
            <div class="gap-header">
              <div class="gap-kp-info">
                <span class="gap-kp-name">{{ group.kp_name }}</span>
                <span class="gap-material-name" v-if="group.material_name">{{ group.material_name }}</span>
              </div>
              <div class="gap-header-right">
                <span class="gap-dim-count">{{ group.dimensions.length }} 个记录维度</span>
                <span class="report-link-hint">{{ reportOpeningKpId === group.kp_id ? '读取中…' : '查看学习报告 →' }}</span>
              </div>
            </div>
            <div class="gap-focus-row">
              <span class="dim-tag" :class="getDimensionClass(group.focus?.dimension)">复习重点 · {{ group.focus?.dimension }}</span>
              <strong>{{ group.focus?.score }}<small>/10</small></strong>
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
                <span v-else>{{ group.dimensions.every(d => d.status === 'reviewing') ? '继续复习' : '开始复习' }}</span>
              </button>
              <button
                v-if="group.dimensions.every(d => d.status === 'resolved')"
                class="action-btn action-btn--reopen"
                @click.stop="startReviewKp(group)"
              >重新打开</button>
              <button
                v-if="!group.dimensions.some(d => d.status === 'open') && !group.dimensions.every(d => d.status === 'resolved')"
                class="action-btn action-btn--master"
                @click.stop="startReviewKp(group)"
              >全部标记已掌握</button>
            </div>
          </article>
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

      <!-- 学习历史 Tab（历史报告 + 历史会话） -->
      <div v-if="activeTab === 'reports'" class="tab-content">
        <div v-if="loadingHistory" class="loading-state">
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
          <p>登录后查看学习历史</p>
          <button class="upload-btn" @click="router.push('/login')">
            去登录
          </button>
        </div>

        <!-- 空状态 -->
        <div v-else-if="historyCards.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <p>暂无学习历史，快去选择一个知识点开始费曼学习吧</p>
          <button class="start-btn" @click="router.push('/select')">
            开始学习
          </button>
        </div>

        <!-- 学习历史：顶部统计 + 时间轴 -->
        <template v-else>

        <!-- 顶部统计模块 -->
        <section v-if="userStats" class="history-module">
          <div class="history-module-head">
            <div class="history-module-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            </div>
            <div>
              <h2 class="history-module-title">学习历史</h2>
              <p class="history-module-sub">查看你的学习记录、能力变化与历史报告</p>
            </div>
          </div>
          <div class="history-stat-grid">
            <div class="history-stat-card">
              <div class="history-stat-label">学习次数</div>
              <div class="history-stat-value">{{ userStats.total_sessions }}</div>
              <div class="history-stat-foot">累计学习</div>
            </div>
            <div class="history-stat-card">
              <div class="history-stat-label">平均得分</div>
              <div class="history-stat-value">{{ userStats.avg_total_score }}</div>
              <div class="history-stat-foot">满分 40</div>
            </div>
            <div class="history-stat-card">
              <div class="history-stat-label">已学习知识点</div>
              <div class="history-stat-value">{{ userStats.total_kps_learned }}</div>
              <div class="history-stat-foot">已接触</div>
            </div>
            <div class="history-stat-card">
              <div class="history-stat-label">学习记录</div>
              <div class="history-stat-value">{{ historyCards.length }}</div>
              <div class="history-stat-foot">历史记录</div>
            </div>
          </div>
        </section>

        <!-- 学习时间轴 -->
        <section class="history-timeline-section">
          <div class="history-timeline-head">
            <h3 class="history-timeline-title">学习时间轴</h3>
            <span class="history-timeline-count">共 {{ historyCards.length }} 条记录</span>
          </div>

          <div class="history-timeline">
            <div
              v-for="card in historyCards"
              :key="card.key"
              class="history-timeline-item"
              :class="historyTierClass(card.total_score)"
            >
              <div class="history-timeline-date">
                <span class="ht-cal-month">{{ timelineMonth(card.created_at) }}</span>
                <span class="ht-cal-day">{{ timelineDay(card.created_at) }}</span>
              </div>
              <div class="history-timeline-dot"></div>

              <div class="history-course-card">
                <!-- 卡片头部 -->
                <div class="history-course-head">
                  <div class="history-course-title-wrap">
                    <div class="history-course-icon" :class="historyIconClass(card.total_score)">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                        <path d="M6 12v5c3 3 9 3 12 0v-5" />
                      </svg>
                    </div>
                    <div>
                      <div class="history-course-title-row">
                        <h4 class="history-course-name">{{ card.kp_name }}</h4>
                        <span class="history-badge" :class="historyBadgeClass(card.total_score)">
                          {{ historyBadgeText(card.total_score) }}
                        </span>
                      </div>
                      <p class="history-course-meta">{{ card.material_name || '当前教材' }} · {{ formatDate(card.created_at) }}</p>
                    </div>
                  </div>

                  <div v-if="card.total_score !== null" class="history-course-score">
                    <span class="history-score-label">得分</span>
                    <span class="history-score-num">{{ card.total_score }}</span>
                    <span class="history-score-total">/40</span>
                  </div>
                  <div v-else class="history-course-score history-course-score--none">
                    <span>暂无评分</span>
                  </div>
                </div>

                <!-- 能力评估：环形进度 -->
                <div v-if="card.dimensions.length" class="history-ability">
                  <div class="history-ability-title">能力评估</div>
                  <div class="history-ability-grid">
                    <div v-for="dim in card.dimensions" :key="dim.name" class="history-ring-item">
                      <div class="history-ring">
                        <svg class="history-ring-svg" viewBox="0 0 80 80">
                          <circle cx="40" cy="40" r="32" stroke="#eef2ff" stroke-width="8" fill="none"/>
                          <circle
                            cx="40" cy="40" r="32"
                            :stroke="dimColor(dim.score)"
                            stroke-width="8"
                            fill="none"
                            stroke-dasharray="200.96"
                            :stroke-dashoffset="ringOffset(dim.score)"
                            stroke-linecap="round"
                          />
                        </svg>
                        <span class="history-ring-score">{{ dim.score }}</span>
                      </div>
                      <div class="history-ring-label">{{ dim.name }}</div>
                    </div>
                  </div>
                </div>
                <div v-else class="history-ability history-ability--empty">
                  本次学习暂未生成完整能力评估数据，完成学习任务后将自动更新。
                </div>

                <!-- 操作按钮 -->
                <div class="history-course-actions">
                  <button
                    class="history-btn history-btn--ghost"
                    :disabled="!card.session"
                    :title="card.session ? '查看历史会话' : '暂无会话记录'"
                    @click="card.session && viewSessionDetail(card.session)"
                  >
                    历史会话
                  </button>
                  <button
                    class="history-btn history-btn--primary"
                    :disabled="!card.report"
                    :title="card.report ? '查看学习报告' : '暂无学习报告'"
                    @click="card.report && viewReportDetail(card.report)"
                  >
                    学习报告
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        </template>
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
      :loading="reportDetailLoading"
      show-review-action
      :review-list-added="selectedReport?.review_list_added"
      :review-adding="reportReviewAdding"
      @close="showReportDetail = false"
      @add-review="addSelectedReportToReviewList"
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

    <!-- 轻量 Toast 提示 -->
    <Transition name="toast-fade">
      <div v-if="toastVisible" class="profile-toast">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span>{{ toastText }}</span>
      </div>
    </Transition>
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
    },
    /**
     * 格式化下次复习时间：「下次复习：X月X日 · 剩余X天」
     * 逾期天数用负值/红字标识
     */
    formatNextReview(dateStr) {
      if (!dateStr) return null
      const target = new Date(dateStr)
      const now = new Date()
      const month = target.getMonth() + 1
      const day = target.getDate()
      const diffMs = target.getTime() - now.getTime()
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
      let remainText
      if (diffDays > 0) {
        remainText = `剩余 ${diffDays} 天`
      } else if (diffDays === 0) {
        remainText = '今天到期'
      } else {
        remainText = `已逾期 ${Math.abs(diffDays)} 天`
      }
      return `下次复习：${month}月${day}日 · ${remainText}`
    },
    isOverdue(dateStr) {
      if (!dateStr) return false
      return new Date(dateStr).getTime() < Date.now()
    },
    formatLastReviewed(dateStr) {
      if (!dateStr) return null
      const d = new Date(dateStr)
      return `上次复习：${d.getMonth() + 1}月${d.getDate()}日`
    },
    /* ===== 学习历史：环形进度 / 徽章 / 图标 辅助方法 ===== */
    // 环形进度偏移量：分数 0-10，周长 200.96
    ringOffset(score) {
      const s = Math.max(0, Math.min(10, Number(score) || 0))
      return (200.96 * (1 - s / 10)).toFixed(2)
    },
    // 环形进度颜色：≥8 绿、≥6 琥珀、否则红
    dimColor(score) {
      if (score >= 8) return '#22c55e'
      if (score >= 6) return '#f59e0b'
      return '#ef4444'
    },
    // 时间轴节点状态：success(≥32) / default(有分) / empty(无分)
    historyTierClass(score) {
      if (score === null || score === undefined) return 'history-tier-empty'
      if (score >= 32) return 'history-tier-success'
      return 'history-tier-default'
    },
    // 掌握程度徽章样式
    historyBadgeClass(score) {
      if (score === null || score === undefined) return 'history-badge--none'
      if (score >= 32) return 'history-badge--good'
      return 'history-badge--weak'
    },
    // 掌握程度徽章文案
    historyBadgeText(score) {
      if (score === null || score === undefined) return '暂无评估'
      if (score >= 32) return '掌握良好'
      return '需巩固'
    },
    // 卡片图标状态
    historyIconClass(score) {
      if (score === null || score === undefined) return 'history-icon--none'
      if (score >= 32) return 'history-icon--good'
      return 'history-icon--weak'
    },
    // 时间轴日历框：月份色条 + 大号日数
    timelineMonth(dateStr) {
      if (!dateStr) return ''
      return `${new Date(dateStr).getMonth() + 1}月`
    },
    timelineDay(dateStr) {
      if (!dateStr) return ''
      return String(new Date(dateStr).getDate())
    }
  }
}
</script>

<style scoped>
.profile-page {
  flex: 1 0 auto;
  min-height: 100dvh;
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
  width: 100%;
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
  flex-direction: row;
  align-items: center;
  gap: 16px;
  padding: 18px 22px;
  background: #FFFFFF;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
  text-align: left;
}

.user-avatar-large {
  width: 56px;
  height: 56px;
  flex: 0 0 56px;
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
  text-align: left;
}

.record-link {
  padding: 8px 12px;
  border: 1px solid #cbdaf5;
  border-radius: 8px;
  color: #245bd4;
  background: #f6f9ff;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.record-link:hover { background: #eaf1ff; }
.profile-quick-actions { display: flex; align-items: center; gap: 8px; }
.record-link--favorite { color: #a35f00; border-color: #edd19b; background: #fff9ec; }
.record-link--favorite:hover { background: #fff2d5; }

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

.review-gap-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.dim-review-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.review-time-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: rgba(37, 99, 235, 0.08);
  color: #2563EB;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.review-time-tag.review-time--overdue {
  background: rgba(239, 68, 68, 0.1);
  color: #DC2626;
}

.last-review-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: #F1F5F9;
  color: #64748B;
  border-radius: 6px;
  font-size: 11px;
}

.review-count-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
  border-radius: 6px;
  font-size: 11px;
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
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms, transform 150ms;
}
.review-gap-count { display: block; margin: -2px 0 8px; color: #7C8BA1; font-size: 11px; }
.gap-card:hover { border-color: #AFC6EF; box-shadow: 0 8px 24px rgba(37, 99, 235, .08); transform: translateY(-1px); }
.gap-card:focus-visible { outline: 3px solid #BFDBFE; outline-offset: 2px; }

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

.report-link-hint { color: #2563EB; font-size: 12px; font-weight: 600; }
.gap-focus-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 15px 16px; }
.gap-focus-row strong { color: #1E293B; font-size: 20px; }
.gap-focus-row strong small { margin-left: 2px; color: #94A3B8; font-size: 11px; font-weight: 500; }

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
  margin: 0 16px 16px;
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

@media (max-width: 767px) {
  .user-card { flex-wrap: wrap; padding: 16px; }
  .profile-quick-actions { width: 100%; flex-direction: column; align-items: stretch; }
  .record-link { width: 100%; }
}

/* 轻量 Toast */
.profile-toast {
  position: fixed;
  top: 72px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: rgba(15, 23, 42, 0.92);
  color: #FFFFFF;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  z-index: 200;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}

/* ===== 学习历史：顶部统计模块 + 时间轴 ===== */
.history-module {
  background: linear-gradient(135deg, #eaf4ff 0%, #d9ecff 100%);
  border-radius: 15px;
  padding: 15px 18px;
  margin-bottom: 20px;
  box-shadow: 0 10px 30px rgba(99, 102, 241, 0.08);
}
.history-module-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 11px;
}
.history-module-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6366f1;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.12);
  flex: none;
}
.history-module-icon svg {
  width: 15px;
  height: 15px;
}
.history-module-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1E293B;
}
.history-module-sub {
  margin: 2px 0 0;
  color: #64748B;
  font-size: 11px;
}
.history-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
}
.history-stat-card {
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  padding: 8px 12px;
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.06);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.history-stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 26px rgba(99, 102, 241, 0.12);
}
.history-stat-label {
  color: #64748B;
  font-size: 10.5px;
  margin-bottom: 2px;
}
.history-stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1E293B;
  line-height: 1.2;
}
.history-stat-foot {
  margin-top: 2px;
  font-size: 10.5px;
  color: #94A3B8;
}

/* 时间轴外层 */
.history-timeline-section { display: block; }
.history-timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 11px;
}
.history-timeline-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #1E293B;
}
.history-timeline-count {
  font-size: 11px;
  color: #94A3B8;
}

/* 时间轴主线 */
.history-timeline {
  position: relative;
  padding-left: 92px;
}
.history-timeline::before {
  content: "";
  position: absolute;
  left: 68px;
  top: 7px;
  bottom: 7px;
  width: 2px;
  background: #2563EB;
  border-radius: 2px;
}
.history-timeline-item {
  position: relative;
  padding-bottom: 14px;
}
.history-timeline-item:last-child { padding-bottom: 0; }
/* 时间轴日历框：位于主线左侧 */
.history-timeline-date {
  position: absolute;
  left: -78px;
  top: 1px;
  width: 44px;
  border-radius: 7px;
  overflow: hidden;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.12);
  z-index: 2;
}
.ht-cal-month {
  display: block;
  background: #2563EB;
  color: #fff;
  font-size: 9.5px;
  font-weight: 600;
  text-align: center;
  padding: 2px 0;
  line-height: 1.2;
}
.ht-cal-day {
  display: block;
  color: #1E293B;
  font-size: 15px;
  font-weight: 700;
  text-align: center;
  padding: 2px 0 4px;
  line-height: 1.1;
}
/* 按掌握程度变换月份色条 */
.history-tier-success .ht-cal-month { background: #2563EB; }
.history-tier-empty .ht-cal-month { background: #2563EB; }
.history-timeline-dot {
  position: absolute;
  left: -24px;
  top: 6px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #2563EB;
  box-shadow: 0 0 0 2.5px rgba(37, 99, 235, 0.15);
  transform: translateX(-50%);
  z-index: 1;
}
.history-tier-success .history-timeline-dot {
  border-color: #2563EB;
  box-shadow: 0 0 0 2.5px rgba(37, 99, 235, 0.15);
}
.history-tier-empty .history-timeline-dot {
  border-color: #2563EB;
  box-shadow: 0 0 0 2.5px rgba(37, 99, 235, 0.15);
}

/* 课程卡片：背景与边框对齐对话内诊断报告预览卡片 */
.history-course-card {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 13px;
  padding: 9px 13px;
  max-width: 760px;
  box-shadow: 0px 10px 15px -3px rgba(0, 0, 0, 0.1), 0px 4px 6px -4px rgba(0, 0, 0, 0.1);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  overflow: hidden;
}
.history-course-card:hover {
  transform: translateY(-3px);
  box-shadow: 0px 16px 26px -6px rgba(37, 99, 235, 0.16), 0px 4px 6px -4px rgba(0, 0, 0, 0.1);
}
.history-course-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 9px;
}
.history-course-title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}
.history-course-icon {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex: none;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.18);
}
.history-course-icon svg {
  width: 15px;
  height: 15px;
}
.history-icon--weak { background: #2563EB; }
.history-icon--good { background: #2563EB; }
.history-icon--none { background: #2563EB; box-shadow: 0 6px 14px rgba(37, 99, 235, 0.18); }
.history-course-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}
.history-course-name {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #1E293B;
}
.history-badge {
  font-size: 10.5px;
  padding: 1.5px 7px;
  border-radius: 999px;
  font-weight: 500;
  white-space: nowrap;
}
.history-badge--good { background: #ECFDF5; color: #0F8A5F; }
.history-badge--weak { background: #EFF6FF; color: #2563EB; }
.history-badge--none { background: #F1F5F9; color: #64748B; }
.history-course-meta {
  margin: 2px 0 0;
  color: #94A3B8;
  font-size: 11px;
}

/* 得分 */
.history-course-score {
  display: flex;
  align-items: baseline;
  gap: 3px;
  flex: none;
}
.history-score-label {
  font-size: 11px;
  color: #94A3B8;
}
.history-score-num {
  font-size: 19px;
  font-weight: 700;
  color: #1E293B;
  line-height: 1;
}
.history-score-total {
  font-size: 11px;
  color: #94A3B8;
}
.history-course-score--none span {
  font-size: 11px;
  color: #94A3B8;
}

/* 能力评估：环形进度 */
.history-ability {
  background: #F8FAFC;
  border-radius: 11px;
  padding: 9px 11px;
  margin-bottom: 9px;
}
.history-ability-title {
  font-size: 11px;
  color: #64748B;
  font-weight: 500;
  margin-bottom: 8px;
}
.history-ability-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
}
.history-ring-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}
.history-ring {
  position: relative;
  width: 50px;
  height: 50px;
}
.history-ring-svg {
  width: 50px;
  height: 50px;
  transform: rotate(-90deg);
}
.history-ring-svg circle {
  transition: stroke-dashoffset 0.8s ease;
}
.history-ring-score {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #334155;
  font-size: 13px;
}
.history-ring-label {
  font-size: 10.5px;
  color: #64748B;
  text-align: center;
}
.history-ability--empty {
  color: #94A3B8;
  font-size: 11px;
  line-height: 1.6;
}

/* 操作按钮 */
.history-course-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.history-btn {
  transition: all 0.2s ease;
  border-radius: 8px;
  padding: 6px 13px;
  font-size: 11.5px;
  font-weight: 500;
  flex: none;
}
.history-btn--primary {
  background: #2563EB;
  color: #fff;
}
.history-btn--primary:hover:not(:disabled) {
  background: #1D4ED8;
  box-shadow: 0 8px 20px rgba(37, 99,235, 0.3);
}
.history-btn--ghost {
  background: #F1F5F9;
  color: #475569;
}
.history-btn--ghost:hover:not(:disabled) {
  background: #E2E8F0;
}
.history-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 860px) {
  .history-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .history-ability-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
  .history-course-head { flex-direction: column; align-items: flex-start; }
  /* 小屏：隐藏左侧日期列，时间轴回退为左侧细线 */
  .history-timeline { padding-left: 24px; }
  .history-timeline::before { left: 7px; }
  .history-timeline-date { display: none; }
  .history-timeline-dot { left: -17px; }
  .history-course-card { max-width: none; }
}
</style>
