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
  MOCK_KP_CREATE,
  MOCK_KP_UPDATE,
  MOCK_KP_DELETE,
  MOCK_KP_REGENERATE
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

http.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const message =
      err?.response?.data?.detail ||
      err?.response?.data?.msg ||
      err?.message ||
      '网络异常，请稍后重试'
    return Promise.reject(new Error(message))
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
      return MOCK_GREETING_DYNAMIC.data
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

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
