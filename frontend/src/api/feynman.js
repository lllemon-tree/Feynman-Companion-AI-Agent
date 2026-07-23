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
  MOCK_SESSIONS
} from './mockData'

const LEGACY_USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const USE_FEYNMAN_MOCK = import.meta.env.VITE_USE_FEYNMAN_MOCK == null
  ? LEGACY_USE_MOCK
  : import.meta.env.VITE_USE_FEYNMAN_MOCK === 'true'
const USE_MATERIAL_MOCK = import.meta.env.VITE_USE_MATERIAL_MOCK == null
  ? LEGACY_USE_MOCK
  : import.meta.env.VITE_USE_MATERIAL_MOCK === 'true'
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

    if (err?.response?.status === 401) {
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

export async function fetchGreeting(kpId = null) {
  if (USE_FEYNMAN_MOCK) {
    await delay(400)
    if (kpId) {
      return MOCK_GREETING_MAP[kpId] || MOCK_GREETING_DYNAMIC.data
    }
    return MOCK_GREETING.data
  }
  const params = kpId ? { kp_id: kpId } : {}
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
