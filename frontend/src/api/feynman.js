import axios from 'axios'
import {
  MOCK_FOLLOW_UP,
  MOCK_GENERATE_REPORT,
  MOCK_GREETING,
  MOCK_MATERIAL_STATUS_DONE,
  MOCK_MATERIAL_STATUS_GENERATING,
  MOCK_MATERIAL_STATUS_FAILED,
  MOCK_KNOWLEDGE_TREE,
  MOCK_KP_DETAIL,
  MOCK_GREETING_DYNAMIC,
  MOCK_GREETING_MAP,
  MOCK_KP_CREATE,
  MOCK_KP_UPDATE,
  MOCK_KP_DELETE,
  MOCK_KP_REGENERATE,
  MOCK_AUTH_LOGIN,
  MOCK_AUTH_REGISTER,
  MOCK_AUTH_CURRENT,
  MOCK_RAG_RETRIEVE,
  MOCK_SESSIONS,
  MOCK_USER_PROFILE,
  MOCK_USER_PROFILE_EMPTY,
  MOCK_USER_PROFILE_SAVE,
  MOCK_GAPS,
  MOCK_GAPS_STATS,
  MOCK_GAP_UPDATE,
  MOCK_REPORTS,
  MOCK_REPORT_DETAIL,
  MOCK_USER_STATS,
  MOCK_REVIEW_START_NEW,
  MOCK_REVIEW_START_RESUMED,
  MOCK_REVIEW_START_NO_GAPS,
  MOCK_REVIEW_RESULT_ACTIVE,
  MOCK_REVIEW_RESULT_COMPLETED,
  MOCK_REVIEW_NOT_FOUND,
  MOCK_REVIEW_GREETING,
  MOCK_REVIEW_DUE_GAPS_EXTENDED
} from './mockData'

const LEGACY_USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const USE_FEYNMAN_MOCK = String(import.meta.env.VITE_USE_FEYNMAN_MOCK).toLowerCase() === 'true'
const USE_MATERIAL_MOCK = String(import.meta.env.VITE_USE_MATERIAL_MOCK).toLowerCase() === 'true'
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 60000)

const http = axios.create({
  baseURL: BASE_URL,
  timeout: API_TIMEOUT_MS
})

// 请求拦截器：自动携带Authorization Token
http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('feynman_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (err) => {
    return Promise.reject(err)
  }
)

http.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const responseData = err?.response?.data
    const message =
      responseData?.detail ||
      responseData?.msg ||
      responseData?.error ||
      err?.message ||
      '网络异常，请稍后重试'

    const requestUrl = err?.config?.url || ''
    const isCredentialRequest =
      requestUrl.includes('/auth/login') ||
      requestUrl.includes('/auth/register')
    const hadToken = Boolean(localStorage.getItem('feynman_token'))

    if (err?.response?.status === 401 && hadToken && !isCredentialRequest) {
      localStorage.removeItem('feynman_token')
      localStorage.removeItem('feynman_user')
      window.location.href = '/login'
    }

    const error = new Error(message)
    if (err?.response?.status) {
      error.status = err.response.status
    }
    return Promise.reject(error)
  }
)

export async function chatWithAgent(sessionId, userInput, kpId) {
  if (USE_FEYNMAN_MOCK) {
    return mockChat(sessionId, userInput)
  }
  const data = await http.post('/feynman/chat', {
    session_id: sessionId,
    kp_id: kpId,
    user_input: userInput
  })
  return data?.data
}

export async function fetchGreeting(kpId = null, sessionId = null) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    // 复习场景：传入 session_id 时返回包含重点维度提示的复习引导语
    if (sessionId) {
      return MOCK_REVIEW_GREETING.data
    }
    if (kpId) {
      return MOCK_GREETING_MAP[kpId] || MOCK_GREETING_DYNAMIC.data
    }
    return MOCK_GREETING.data
  }
  // 复习场景：带上 session_id，后端返回含复习重点的引导语
  const params = {}
  if (kpId) params.kp_id = kpId
  if (sessionId) params.session_id = sessionId
  const data = await http.get('/feynman/greeting', { params })
  return data?.data
}

export async function resetFeynmanSession(sessionId) {
  if (USE_FEYNMAN_MOCK) {
    mockCallCount.delete(sessionId)
    return { session_id: sessionId, reset: true }
  }
  const data = await http.post('/feynman/reset', {
    session_id: sessionId
  })
  return data?.data
}

export async function uploadMaterial(file, subject, name, onProgress) {
  if (USE_MATERIAL_MOCK) {
    if (onProgress) {
      for (let i = 0; i <= 100; i += 10) {
        await delay(100)
        onProgress(i)
      }
    }
    await delay(200)
    return { material_id: 'mat-' + Date.now(), status: 'parsing' }
  }
  const formData = new FormData()
  formData.append('file', file)
  formData.append('subject', subject)
  formData.append('name', name)
  const data = await http.post('/material/upload', formData, {
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(percent)
      }
    }
  })
  return data?.data
}

export async function getMaterialStatus(materialId) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    if (materialId === 'mat-generating') {
      const storageKey = `feynman_material_progress_${materialId}`
      let progress = parseFloat(localStorage.getItem(storageKey)) || 0.6
      if (progress >= 1) {
        return {
          material_id: 'mat-generating',
          status: 'done',
          step: '完成',
          progress: 1,
          error: null
        }
      }
      progress = Math.min(1, progress + Math.random() * 0.08)
      localStorage.setItem(storageKey, progress.toString())
      
      let step = 'rubric 生成中'
      let status = 'generating'
      if (progress >= 1) {
        status = 'done'
        step = '完成'
        progress = 1
      } else if (progress < 0.25) {
        step = '解析中'
        status = 'parsing'
      } else if (progress < 0.5) {
        step = '分块中'
        status = 'chunking'
      } else if (progress < 0.75) {
        step = '抽取中'
        status = 'extracting'
      }
      
      return {
        material_id: 'mat-generating',
        status,
        step,
        progress,
        error: null
      }
    } else if (materialId === 'mat-failed') {
      return MOCK_MATERIAL_STATUS_FAILED.data
    }
    return MOCK_MATERIAL_STATUS_DONE.data
  }
  const data = await http.get(`/material/${materialId}/status`)
  return data?.data
}

export async function retryMaterial(materialId) {
  const data = await http.post(`/material/${materialId}/retry`)
  return data?.data
}

export async function getKnowledgeTree(subject) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    return MOCK_KNOWLEDGE_TREE.data
  }
  const data = await http.get('/material/tree', { params: { subject } })
  return data?.data
}

export async function fetchSubjects() {
  if (USE_MATERIAL_MOCK) {
    await delay(300)
    return ['计算机', '数学', '政治']
  }
  const data = await http.get('/material/subjects')
  return data?.data
}

export async function getKpDetail(kpId) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    return MOCK_KP_DETAIL.data
  }
  const data = await http.get(`/kp/${kpId}`)
  return data?.data
}

export async function createKp(chapterId, name, pageStart, pageEnd) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    return MOCK_KP_CREATE.data
  }
  const data = await http.post('/kp', {
    chapter_id: chapterId,
    name,
    page_start: pageStart,
    page_end: pageEnd,
    summary: ''
  })
  return data?.data
}

export async function updateKp(kpId, updates) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    if (updates.page_start || updates.page_end) {
      return MOCK_KP_UPDATE.data
    }
    return { kp_id: kpId, regenerate_triggered: false, status: 'done' }
  }
  const data = await http.patch(`/kp/${kpId}`, updates)
  return data?.data
}

export async function deleteKp(kpId) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    return MOCK_KP_DELETE.data
  }
  const data = await http.delete(`/kp/${kpId}`)
  return data?.data
}

export async function regenerateKp(kpId) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    return MOCK_KP_REGENERATE.data
  }
  const data = await http.post(`/kp/${kpId}/regenerate`)
  return data?.data
}

const mockCallCount = new Map()

async function mockChat(sessionId, userInput) {
  await delay(900 + Math.random() * 600)

  const count = mockCallCount.get(sessionId) || 0
  const next = count + 1
  mockCallCount.set(sessionId, next)

  if (next >= 3) {
    return MOCK_GENERATE_REPORT.data
  }
  return MOCK_FOLLOW_UP.data
}

// Mock用户存储（内存中保存注册用户）
const mockUsers = new Map([
  ['teststudent', { username: 'teststudent', password: '123456', user_id: 'user-demo' }]
])

// Auth模块API

/**
 * 用户登录
 * @param {string} username - 用户名
 * @param {string} password - 密码
 */
export async function login(username, password) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    // Mock模式：检查用户是否存在且密码正确
    const user = mockUsers.get(username)
    if (user && user.password === password) {
      return {
        token: `mock-token-${username}-${Date.now()}`,
        user_id: user.user_id,
        username: user.username
      }
    }
    // 返回401错误
    const error = new Error('用户名或密码错误')
    error.status = 401
    return Promise.reject(error)
  }
  const data = await http.post('/auth/login', { username, password })
  return data?.data
}

/**
 * 用户注册
 * @param {string} username - 用户名
 * @param {string} password - 密码
 */
export async function register(username, password) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    // Mock模式：检查用户名是否已存在
    if (mockUsers.has(username)) {
      const error = new Error('该用户名已被注册')
      error.status = 400
      return Promise.reject(error)
    }
    // 创建新用户
    const userId = 'user-' + Date.now()
    mockUsers.set(username, { username, password, user_id: userId })
    return { user_id: userId }
  }
  const data = await http.post('/auth/register', { username, password })
  return data?.data
}

/**
 * 获取当前登录用户信息
 */
export async function getCurrentUser() {
  if (USE_FEYNMAN_MOCK) {
    await delay(300)
    // Mock模式：检查是否有token和用户信息
    const token = localStorage.getItem('feynman_token')
    const userStr = localStorage.getItem('feynman_user')
    if (token && userStr) {
      const user = JSON.parse(userStr)
      return {
        user_id: user.user_id,
        username: user.username
      }
    }
    // 未登录返回401错误
    const error = new Error('请先登录')
    error.status = 401
    return Promise.reject(error)
  }
  const data = await http.get('/auth/current')
  return data?.data
}

// RAG向量检索模块API

/**
 * 教材语义检索
 * @param {string} materialId - 教材ID
 * @param {string} query - 讲解文本
 * @param {number} topK - 返回数量，默认3
 */
export async function retrieveMaterialChunks(materialId, query, topK = 3) {
  if (USE_MATERIAL_MOCK) {
    await delay(500)
    return MOCK_RAG_RETRIEVE.data
  }
  const data = await http.get(`/material/${materialId}/retrieve`, {
    params: { query, top_k: topK }
  })
  return data?.data
}

/**
 * 手动触发教材向量重生成
 * @param {string} materialId - 教材ID
 */
export async function rebuildMaterialEmbedding(materialId) {
  if (USE_MATERIAL_MOCK) {
    await delay(300)
    return { material_id: materialId }
  }
  const data = await http.post(`/material/${materialId}/embedding/rebuild`)
  return data?.data
}

// 会话持久化模块API

/**
 * 获取历史会话列表（P1）
 */
export async function getSessionList() {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    return MOCK_SESSIONS.data
  }
  const data = await http.get('/feynman/sessions')
  return data?.data
}

/**
 * 查询单条历史会话详情（P1）
 * @param {string} sessionId - 会话ID
 */
export async function getSessionDetail(sessionId) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    return {
      session_id: sessionId,
      kp_name: 'Dijkstra 算法',
      material_title: '数据结构教材',
      chat_history: [],
      report_data: null,
      created_at: '2026-07-20T10:30:00'
    }
  }
  const data = await http.get(`/feynman/sessions/${sessionId}`)
  return data?.data
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 学情画像模块API

/**
 * 获取当前用户学情
 */
export async function getUserProfile() {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    // 可通过 localStorage 判断是否为首次注册
    const isFirstTime = localStorage.getItem('feynman_profile_setup_done') !== 'true'
    return isFirstTime ? MOCK_USER_PROFILE_EMPTY.data : MOCK_USER_PROFILE.data
  }
  const data = await http.get('/user/profile')
  return data?.data
}

/**
 * 保存/更新学情
 * @param {object} profileData - 学情数据
 */
export async function saveUserProfile(profileData) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    localStorage.setItem('feynman_profile_setup_done', 'true')
    return MOCK_USER_PROFILE_SAVE.data
  }
  const data = await http.post('/user/profile', profileData)
  return data?.data
}

/**
 * 更新学情（部分更新）
 * @param {object} updates - 要更新的字段
 */
export async function updateUserProfile(updates) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    return MOCK_USER_PROFILE_SAVE.data
  }
  const data = await http.patch('/user/profile', updates)
  return data?.data
}

// 知识漏洞库模块API

/**
 * 获取知识漏洞列表
 * @param {string} status - 可选，漏洞状态 (open/reviewing/resolved)
 */
export async function getGaps(status = null) {
  if (USE_FEYNMAN_MOCK) {
    await delay(500)
    let items = MOCK_GAPS.data.items
    if (status) {
      items = items.filter(g => g.status === status)
    }
    return {
      items,
      total: items.length,
      page: 1,
      page_size: 20
    }
  }
  const params = status ? { status } : {}
  const data = await http.get('/gaps', { params })
  return data?.data
}

/**
 * 更新漏洞状态
 * @param {string} gapId - 漏洞ID
 * @param {string} status - 新状态
 *
 * PRD 6.5 规则：
 * - status=resolved：用户手动确认掌握，写入 resolution_source=manual 和 resolved_at；
 * - status=open：用户主动重新加入待复习，清空解决信息；
 * - 前端开始复习不再直接 PATCH reviewing，统一调用 /reviews/start；
 * - 直接 PATCH status=reviewing 返回 400（规则5）；
 * - gap 正处于 active 复习记录时，手动修改为 open/resolved 返回 409（规则6）。
 */
export async function updateGapStatus(gapId, status) {
  if (USE_FEYNMAN_MOCK) {
    await delay(300)
    // PRD 6.5 规则5：直接 PATCH status=reviewing 返回 400，避免绕过 review_attempt
    if (status === 'reviewing') {
      return Promise.reject(mockError({ code: 400, msg: 'cannot patch to reviewing directly, use /reviews/start', data: null }))
    }
    // PRD 6.5 规则6：gap 正处于 active 复习记录时，手动修改为 open/resolved 返回 409
    if (mockActiveReviewGapIds.has(gapId) && (status === 'open' || status === 'resolved')) {
      return Promise.reject(mockError({ code: 409, msg: 'gap is in an active review, complete the review first', data: null }))
    }
    // 正常修改：成功后从 active gap 集合移除（resolved 表示已掌握）
    if (status === 'resolved') {
      mockActiveReviewGapIds.delete(gapId)
    }
    return {
      gap_id: gapId,
      status
    }
  }
  const data = await http.patch(`/gaps/${gapId}`, { status })
  return data?.data
}

/**
 * 获取漏洞统计数据
 */
export async function getGapsStats() {
  if (USE_FEYNMAN_MOCK) {
    await delay(300)
    return MOCK_GAPS_STATS.data
  }
  const data = await http.get('/gaps/stats')
  return data?.data
}

// 诊断报告模块API

/**
 * 获取历史报告列表
 */
export async function getReports() {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    return MOCK_REPORTS.data
  }
  const data = await http.get('/reports')
  return data?.data
}

/**
 * 获取报告详情
 * @param {string} reportId - 报告ID
 */
export async function getReportDetail(reportId) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    return MOCK_REPORT_DETAIL.data
  }
  const data = await http.get(`/reports/${reportId}`)
  return data?.data
}

/**
 * 获取今日待复习漏洞列表
 * 第八周扩展：返回项含 active_review_id 和 action 字段
 * - active_review_id: 存在未完成复习时返回对应 review_id
 * - action: 无 active 记录时为 'start'，有 active 记录时为 'continue'
 */
export async function getReviewDueGaps() {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    return MOCK_REVIEW_DUE_GAPS_EXTENDED.data
  }
  const data = await http.get('/gaps/review-due')
  return data?.data
}

/**
 * 获取学情统计数据
 */
export async function getUserStats() {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    return MOCK_USER_STATS.data
  }
  const data = await http.get('/user/stats')
  return data?.data
}

// ===== 第八周 复习闭环 API =====

// 内存态 Mock：记录当前用户每个 KP 的 active review，用于模拟 resumed 行为
const mockActiveReviews = new Map() // key: kp_id, value: review start 响应
// 内存态 Mock：记录处于 active 复习中的 gap_id 集合，用于实现 PRD 6.5 规则6
const mockActiveReviewGapIds = new Set()

/**
 * 构建 Mock 异常错误对象（与 http 拦截器行为一致）
 * 真实后端返回 HTTP 4xx/5xx 时，拦截器提取 responseData.msg 作为 message、
 * err.response.status 作为 status。Mock 模式下用相同方式构造，并挂载完整响应体。
 * @param {{code: number, msg: string, data: any}} mockBody - Mock 响应体
 */
function mockError(mockBody) {
  const err = new Error(mockBody.msg)
  err.status = mockBody.code
  err.body = mockBody // 挂载完整 {code, msg, data} 便于调试
  return err
}

/**
 * 开始或继续复习
 * POST /api/v1/reviews/start
 * @param {string} kpId - 知识点ID
 * @param {string} source - 入口来源：'gap' 或 'due'
 * @returns {Promise<object>} 复习记录（含 review_id、session_id、target_gaps 等）
 *
 * 行为：
 * 1. 查询当前用户、当前 KP 的全部 open/reviewing 漏洞；
 * 2. 没有未解决漏洞时返回 409，msg=no unresolved gaps；
 * 3. 已有同 KP 的 active 复习记录时返回原记录，resumed=true；
 * 4. 否则创建 review_attempt 和新的 session_id，并把 open 目标漏洞改为 reviewing；
 * 5. 此时不修改 review_count、last_reviewed_at 和 next_review_at。
 */
export async function startReview(kpId, source = 'gap') {
  if (USE_FEYNMAN_MOCK) {
    await delay(500)
    // Mock：没有未解决漏洞时返回 409（使用 mockData 中定义的标准响应体）
    if (kpId === 'kp-no-gaps') {
      return Promise.reject(mockError(MOCK_REVIEW_START_NO_GAPS))
    }
    // Mock：已有 active 记录时返回 resumed=true（使用 mockData 中定义的 Mock）
    const existing = mockActiveReviews.get(kpId)
    if (existing) {
      // 以定义的 MOCK_REVIEW_START_RESUMED 为模板，保留当前 kp 的动态字段
      const resumed = JSON.parse(JSON.stringify(MOCK_REVIEW_START_RESUMED.data))
      resumed.kp_id = existing.kp_id
      resumed.review_id = existing.review_id
      resumed.session_id = existing.session_id
      resumed.target_gaps = existing.target_gaps
      resumed.baseline_report_id = existing.baseline_report_id
      return resumed
    }
    // Mock：新建复习记录（以 MOCK_REVIEW_START_NEW 为模板）
    const record = JSON.parse(JSON.stringify(MOCK_REVIEW_START_NEW.data))
    record.kp_id = kpId
    record.resumed = false
    mockActiveReviews.set(kpId, record)
    // 记录本次复习涉及的目标 gap_id，用于 PRD 6.5 规则6 判定
    record.target_gaps.forEach(g => mockActiveReviewGapIds.add(g.gap_id))
    return record
  }
  const data = await http.post('/reviews/start', { kp_id: kpId, source })
  return data?.data
}

/**
 * 查询复习结果
 * GET /api/v1/reviews/{review_id}
 * @param {string} reviewId - 复习记录ID
 * @returns {Promise<object>} 复习结果（含 status、dimension_changes 等）
 *
 * dimension_changes 中每项包含：
 * - dimension: 维度名
 * - previous_score / current_score / delta
 * - result: 'mastered' | 'continue' | 'unchanged'
 * - gap_id / gap_status / review_count / next_review_at
 */
export async function getReviewResult(reviewId) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    // Mock：review_id 不属于当前用户时返回 404（使用 mockData 中定义的标准响应体）
    if (reviewId === 'review-not-mine' || reviewId === 'review-not-found') {
      return Promise.reject(mockError(MOCK_REVIEW_NOT_FOUND))
    }
    // Mock：复习仍为 active 时返回 result_report_id=null
    if (reviewId === 'review-active') {
      return MOCK_REVIEW_RESULT_ACTIVE.data
    }
    // Mock：默认返回复习完成结果
    return MOCK_REVIEW_RESULT_COMPLETED.data
  }
  const data = await http.get(`/reviews/${reviewId}`)
  return data?.data
}

/**
 * 重置 Mock 复习状态（仅供 Mock 模式测试使用）
 */
export function _resetMockReviewState() {
  mockActiveReviews.clear()
  mockActiveReviewGapIds.clear()
}
