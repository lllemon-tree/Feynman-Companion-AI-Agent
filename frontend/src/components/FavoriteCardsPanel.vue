<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chatStore'
import {
  createCardFavoriteCollection,
  deleteCardFavoriteCollection,
  getCardFavoriteCollections,
  getCardFavorites,
  removeCardFavorite,
  updateCardFavorite,
  updateCardFavoriteCollection
} from '@/api/feynman'

const router = useRouter()
const chatStore = useChatStore()

const loading = ref(false)
const items = ref([])
const collections = ref([])
const availableTags = ref([])
const query = ref('')
const selectedCollection = ref('')
const selectedTag = ref('')
const sort = ref('recent')
const toast = ref('')
let toastTimer = null

const folderDialogOpen = ref(false)
const editingCollection = ref(null)
const folderForm = ref({ name: '', description: '', color: '#3b6fe8' })
const folderSaving = ref(false)

const editorOpen = ref(false)
const editingFavorite = ref(null)
const favoriteForm = ref({ note: '', tagsText: '', collectionIds: [], isPinned: false })
const favoriteSaving = ref(false)

const total = computed(() => items.value.length)

function notify(message) {
  toast.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2400)
}

async function loadCollections() {
  const data = await getCardFavoriteCollections()
  collections.value = data.items || []
}

async function loadFavorites() {
  loading.value = true
  try {
    const data = await getCardFavorites({
      query: query.value,
      collectionId: selectedCollection.value,
      tag: selectedTag.value,
      sort: sort.value
    })
    items.value = data.items || []
    availableTags.value = data.available_tags || []
  } catch (error) {
    notify(error.message || '收藏内容加载失败')
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadCollections(), loadFavorites()])
  } finally {
    loading.value = false
  }
}

function openCreateFolder() {
  editingCollection.value = null
  folderForm.value = { name: '', description: '', color: '#3b6fe8' }
  folderDialogOpen.value = true
}

function openEditFolder(collection) {
  editingCollection.value = collection
  folderForm.value = {
    name: collection.name,
    description: collection.description || '',
    color: collection.color
  }
  folderDialogOpen.value = true
}

async function saveFolder() {
  if (!folderForm.value.name.trim() || folderSaving.value) return
  folderSaving.value = true
  try {
    const payload = {
      name: folderForm.value.name.trim(),
      description: folderForm.value.description.trim(),
      color: folderForm.value.color
    }
    if (editingCollection.value) {
      await updateCardFavoriteCollection(editingCollection.value.collection_id, payload)
      notify('收藏夹已更新')
    } else {
      await createCardFavoriteCollection(payload)
      notify('收藏夹已创建')
    }
    folderDialogOpen.value = false
    await loadCollections()
  } catch (error) {
    notify(error.message || '收藏夹保存失败')
  } finally {
    folderSaving.value = false
  }
}

async function removeFolder(collection) {
  if (!window.confirm(`删除收藏夹“${collection.name}”？其中的知识卡片仍会保留在“全部收藏”中。`)) return
  try {
    await deleteCardFavoriteCollection(collection.collection_id)
    if (selectedCollection.value === collection.collection_id) selectedCollection.value = ''
    await loadAll()
    notify('收藏夹已删除，卡片仍保留')
  } catch (error) {
    notify(error.message || '收藏夹删除失败')
  }
}

function openFavoriteEditor(item) {
  editingFavorite.value = item
  favoriteForm.value = {
    note: item.note || '',
    tagsText: (item.tags || []).join('，'),
    collectionIds: [...(item.collection_ids || [])],
    isPinned: Boolean(item.is_pinned)
  }
  editorOpen.value = true
}

async function saveFavorite() {
  if (!editingFavorite.value || favoriteSaving.value) return
  favoriteSaving.value = true
  try {
    const tags = favoriteForm.value.tagsText
      .split(/[,，]/)
      .map(item => item.trim())
      .filter(Boolean)
    await updateCardFavorite(editingFavorite.value.favorite_id, {
      note: favoriteForm.value.note,
      tags,
      collection_ids: favoriteForm.value.collectionIds,
      is_pinned: favoriteForm.value.isPinned
    })
    editorOpen.value = false
    await loadAll()
    notify('收藏信息已保存')
  } catch (error) {
    notify(error.message || '收藏信息保存失败')
  } finally {
    favoriteSaving.value = false
  }
}

async function togglePin(item) {
  try {
    await updateCardFavorite(item.favorite_id, { is_pinned: !item.is_pinned })
    await loadFavorites()
  } catch (error) {
    notify(error.message || '置顶操作失败')
  }
}

async function unfavorite(item) {
  if (!window.confirm(`取消收藏“${item.kp_name}”？个人备注和标签也会一并移除。`)) return
  try {
    await removeCardFavorite(item.favorite_id)
    await loadAll()
    notify('已取消收藏')
  } catch (error) {
    notify(error.message || '取消收藏失败')
  }
}

function startStudy(item) {
  chatStore.clearReviewContext()
  chatStore.clearKnowledgeContext()
  chatStore.setSubject(item.material_subject || '')
  chatStore.setMaterial(item.material_id, item.material_name)
  chatStore.setChapter(item.chapter_id, item.chapter_name)
  chatStore.setKnowledgePoint(item.kp_id, item.kp_name)
  router.push('/study')
}

function coverageText(level) {
  return { sufficient: '教材依据完整', partial: '教材部分覆盖', limited: '教材依据有限' }[level] || '教材卡片'
}

function collectionName(collectionId) {
  return collections.value.find(item => item.collection_id === collectionId)?.name || ''
}

let queryTimer = null
watch(query, () => {
  if (queryTimer) clearTimeout(queryTimer)
  queryTimer = setTimeout(loadFavorites, 280)
})
watch([selectedCollection, selectedTag, sort], loadFavorites)
onMounted(loadAll)
</script>

<template>
  <section class="favorites-panel">
    <header class="favorites-hero">
      <div>
        <span class="eyebrow">PERSONAL KNOWLEDGE LIBRARY</span>
        <h2>知识收藏</h2>
        <p>保存真正值得反复使用的知识卡片，并用收藏夹、标签和备注形成自己的知识库。</p>
      </div>
      <div class="hero-count"><strong>{{ total }}</strong><span>张卡片</span></div>
    </header>

    <div class="folder-bar">
      <button class="folder-chip" :class="{ active: !selectedCollection }" @click="selectedCollection = ''">
        全部收藏
      </button>
      <div v-for="folder in collections" :key="folder.collection_id" class="folder-wrap">
        <button class="folder-chip" :class="{ active: selectedCollection === folder.collection_id }" @click="selectedCollection = folder.collection_id">
          <i :style="{ background: folder.color }"></i>{{ folder.name }} <span>{{ folder.item_count }}</span>
        </button>
        <button class="folder-menu" title="编辑收藏夹" @click="openEditFolder(folder)">•••</button>
      </div>
      <button class="new-folder" @click="openCreateFolder">＋ 新建收藏夹</button>
    </div>

    <div class="favorite-toolbar">
      <label class="search-box">
        <span>⌕</span>
        <input v-model="query" placeholder="搜索知识点、教材、标签或备注" />
      </label>
      <select v-model="selectedTag" aria-label="按标签筛选">
        <option value="">全部标签</option>
        <option v-for="tag in availableTags" :key="tag" :value="tag"># {{ tag }}</option>
      </select>
      <select v-model="sort" aria-label="排序方式">
        <option value="recent">最近整理</option>
        <option value="oldest">最早收藏</option>
        <option value="name">按名称</option>
      </select>
    </div>

    <div v-if="loading" class="panel-state">正在整理你的知识收藏…</div>
    <div v-else-if="!items.length" class="panel-state panel-state--empty">
      <div class="empty-star">☆</div>
      <h3>{{ query || selectedCollection || selectedTag ? '没有符合条件的卡片' : '还没有收藏知识卡片' }}</h3>
      <p>学习知识点时，点击知识卡片右上角的“收藏”，它就会出现在这里。</p>
      <button @click="router.push('/select')">去学习知识点</button>
    </div>

    <div v-else class="favorite-grid">
      <article v-for="item in items" :key="item.favorite_id" class="favorite-card" :class="{ 'favorite-card--pinned': item.is_pinned }">
        <div class="card-topline">
          <span class="coverage-badge">{{ coverageText(item.coverage_level) }}</span>
          <div class="card-actions">
            <button :title="item.is_pinned ? '取消置顶' : '置顶'" @click="togglePin(item)">{{ item.is_pinned ? '置顶' : '置顶' }}</button>
            <button title="编辑收藏信息" @click="openFavoriteEditor(item)">整理</button>
            <button class="danger" title="取消收藏" @click="unfavorite(item)">取消收藏</button>
          </div>
        </div>
        <h3>{{ item.kp_name }}</h3>
        <p class="card-path">{{ item.material_name }} · {{ item.chapter_name }}</p>
        <p class="card-summary">{{ item.summary }}</p>
        <div v-if="item.tags.length" class="tag-list">
          <button v-for="tag in item.tags" :key="tag" @click="selectedTag = tag"># {{ tag }}</button>
        </div>
        <div v-if="item.collection_ids.length" class="collection-list">
          <span v-for="collectionId in item.collection_ids" :key="collectionId">{{ collectionName(collectionId) }}</span>
        </div>
        <blockquote v-if="item.note">{{ item.note }}</blockquote>
        <details class="card-content">
          <summary>查看知识卡片内容</summary>
          <div v-for="section in item.sections" :key="section.key" class="mini-section">
            <strong>{{ section.title }}</strong>
            <p v-if="section.content">{{ section.content }}</p>
            <ul v-if="section.bullets?.length"><li v-for="bullet in section.bullets" :key="bullet">{{ bullet }}</li></ul>
          </div>
        </details>
        <div class="card-footer-row">
          <span v-if="item.has_update" class="update-badge">卡片已有新版</span>
          <span v-else>收藏于 {{ new Date(item.created_at).toLocaleDateString() }}</span>
          <button class="study-btn" @click="startStudy(item)">开始费曼讲解 →</button>
        </div>
      </article>
    </div>

    <div v-if="folderDialogOpen" class="dialog-overlay" @click.self="folderDialogOpen = false">
      <form class="dialog" @submit.prevent="saveFolder">
        <h3>{{ editingCollection ? '编辑收藏夹' : '新建收藏夹' }}</h3>
        <label>名称<input v-model="folderForm.name" maxlength="30" required placeholder="例如：Java 核心概念" /></label>
        <label>说明<textarea v-model="folderForm.description" maxlength="120" rows="3" placeholder="这个收藏夹准备收纳什么？"></textarea></label>
        <label class="color-field">标识颜色<input v-model="folderForm.color" type="color" /></label>
        <div class="dialog-actions">
          <button v-if="editingCollection" type="button" class="delete-folder" @click="folderDialogOpen = false; removeFolder(editingCollection)">删除收藏夹</button>
          <span></span><button type="button" @click="folderDialogOpen = false">取消</button>
          <button class="primary" :disabled="folderSaving">{{ folderSaving ? '保存中…' : '保存' }}</button>
        </div>
      </form>
    </div>

    <div v-if="editorOpen" class="dialog-overlay" @click.self="editorOpen = false">
      <form class="dialog dialog--wide" @submit.prevent="saveFavorite">
        <h3>整理「{{ editingFavorite?.kp_name }}」</h3>
        <label>个人备注<textarea v-model="favoriteForm.note" maxlength="1000" rows="5" placeholder="记录它为什么重要、与什么知识有关，或下次复习要注意什么。"></textarea></label>
        <label>标签<input v-model="favoriteForm.tagsText" placeholder="用逗号分隔，例如：Java，面向对象，重点" /></label>
        <fieldset>
          <legend>加入收藏夹</legend>
          <p v-if="!collections.length">还没有自定义收藏夹，可以先保存到“全部收藏”。</p>
          <label v-for="folder in collections" :key="folder.collection_id" class="check-row">
            <input v-model="favoriteForm.collectionIds" type="checkbox" :value="folder.collection_id" />
            <i :style="{ background: folder.color }"></i>{{ folder.name }}
          </label>
        </fieldset>
        <label class="check-row pin-row"><input v-model="favoriteForm.isPinned" type="checkbox" />置顶这张卡片</label>
        <div class="dialog-actions"><span></span><button type="button" @click="editorOpen = false">取消</button><button class="primary" :disabled="favoriteSaving">{{ favoriteSaving ? '保存中…' : '保存整理' }}</button></div>
      </form>
    </div>

    <div v-if="toast" class="favorite-toast">{{ toast }}</div>
  </section>
</template>

<style scoped>
.favorites-panel { display: grid; gap: 20px; }
.favorites-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding: 26px 28px; border: 1px solid #e3eaf5; border-radius: 18px; background: linear-gradient(135deg, #f8fbff, #eef4ff); }
.eyebrow { color: #3970df; font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.favorites-hero h2 { margin: 7px 0 8px; color: #17243d; font-size: 25px; }
.favorites-hero p { max-width: 650px; margin: 0; color: #697991; font-size: 13px; line-height: 1.7; }
.hero-count { display: grid; min-width: 90px; text-align: right; color: #718097; }
.hero-count strong { color: #255fd5; font-size: 31px; line-height: 1; }.hero-count span { margin-top: 5px; font-size: 11px; }
.folder-bar { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.folder-wrap { display: flex; align-items: center; border: 1px solid #dfe6f1; border-radius: 10px; overflow: hidden; background: #fff; }
.folder-chip, .new-folder { min-height: 36px; padding: 0 13px; color: #5f6f87; border: 1px solid #dfe6f1; border-radius: 10px; background: #fff; font-size: 12px; }
.folder-wrap .folder-chip { border: 0; border-radius: 0; }.folder-chip.active { color: #245fd4; border-color: #a9c4f5; background: #edf4ff; font-weight: 700; }
.folder-chip i, .check-row i { width: 8px; height: 8px; display: inline-block; margin-right: 6px; border-radius: 50%; }.folder-chip span { margin-left: 5px; color: #9aa6b7; }
.folder-menu { width: 31px; align-self: stretch; color: #9ba8b9; border-left: 1px solid #edf1f6; background: #fff; }.folder-menu:hover { color: #245fd4; }
.new-folder { color: #2f67d8; border-style: dashed; }
.favorite-toolbar { display: grid; grid-template-columns: minmax(250px, 1fr) 160px 150px; gap: 10px; }
.search-box { display: flex; align-items: center; gap: 8px; padding: 0 13px; border: 1px solid #dfe6f0; border-radius: 11px; background: #fff; }.search-box input { width: 100%; min-height: 40px; border: 0; outline: 0; }
.favorite-toolbar select { min-height: 42px; padding: 0 10px; border: 1px solid #dfe6f0; border-radius: 11px; color: #52647d; background: #fff; }
.panel-state { min-height: 260px; display: grid; place-items: center; color: #8190a5; border: 1px solid #e5ebf4; border-radius: 16px; background: #fff; }
.panel-state--empty { align-content: center; gap: 8px; text-align: center; }.empty-star { color: #9db5e9; font-size: 44px; }.panel-state h3, .panel-state p { margin: 0; }.panel-state p { color: #98a5b7; font-size: 12px; }.panel-state button { margin-top: 8px; padding: 9px 15px; border-radius: 9px; color: #fff; background: #2f68df; }
.favorite-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.favorite-card { display: flex; flex-direction: column; min-height: 300px; padding: 20px; border: 1px solid #e1e8f2; border-radius: 16px; background: #fff; box-shadow: 0 5px 18px rgba(34, 59, 100, .045); }.favorite-card--pinned { border-color: #b9cdf4; box-shadow: 0 7px 22px rgba(45, 99, 205, .09); }
.card-topline, .card-footer-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }.coverage-badge { color: #3b6fd8; font-size: 10px; font-weight: 700; letter-spacing: .03em; }.card-actions { display: flex; gap: 5px; }.card-actions button { padding: 4px 6px; color: #8592a5; font-size: 10px; }.card-actions button:hover { color: #245fd4; }.card-actions .danger:hover { color: #c74444; }
.favorite-card h3 { margin: 12px 0 5px; color: #1d2c46; font-size: 19px; }.card-path { margin: 0 0 13px; color: #8795a9; font-size: 11px; }.card-summary { margin: 0; color: #4e607a; font-size: 13px; line-height: 1.7; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 13px; }.tag-list button { padding: 4px 8px; border-radius: 999px; color: #4770be; background: #eef4ff; font-size: 10px; }
.collection-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }.collection-list span { padding: 3px 7px; border: 1px solid #e1e7f0; border-radius: 6px; color: #78869a; font-size: 9px; background: #fafbfd; }
blockquote { margin: 13px 0 0; padding: 9px 11px; color: #77603f; border-left: 3px solid #e4ba70; background: #fff9ef; font-size: 11px; line-height: 1.6; }
.card-content { margin: 14px 0; color: #5d6f87; font-size: 11px; }.card-content summary { cursor: pointer; color: #3567c8; }.mini-section { padding: 10px 0; border-bottom: 1px solid #edf1f6; }.mini-section p, .mini-section ul { margin: 5px 0 0; line-height: 1.65; }.mini-section ul { padding-left: 17px; }
.card-footer-row { margin-top: auto; padding-top: 13px; border-top: 1px solid #edf1f6; color: #98a4b5; font-size: 10px; }.update-badge { color: #b46c0d; }.study-btn { padding: 8px 11px; border-radius: 8px; color: #fff; background: #2e67dc; font-size: 11px; }
.dialog-overlay { position: fixed; inset: 0; z-index: 500; display: grid; place-items: center; padding: 20px; background: rgba(20, 34, 58, .48); }.dialog { width: min(440px, 100%); display: grid; gap: 15px; padding: 24px; border-radius: 17px; background: #fff; box-shadow: 0 28px 80px rgba(20, 37, 67, .24); }.dialog--wide { width: min(590px, 100%); }.dialog h3 { margin: 0; color: #1c2a43; }.dialog > label { display: grid; gap: 6px; color: #66758c; font-size: 12px; }.dialog input:not([type='checkbox']):not([type='color']), .dialog textarea { width: 100%; padding: 10px 11px; border: 1px solid #dce4ef; border-radius: 9px; outline: 0; resize: vertical; }.dialog input:focus, .dialog textarea:focus { border-color: #7ba3ee; }.color-field { grid-template-columns: 1fr 50px; align-items: center; }.color-field input { width: 50px; height: 32px; padding: 2px; border: 0; }
fieldset { padding: 12px; border: 1px solid #e1e8f2; border-radius: 10px; }fieldset legend { padding: 0 5px; color: #566982; font-size: 12px; }fieldset p { margin: 0; color: #98a4b5; font-size: 11px; }.check-row { display: flex !important; grid-template-columns: none !important; align-items: center; gap: 8px !important; margin-top: 8px; }.pin-row { margin: 0; }
.dialog-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }.dialog-actions span { flex: 1; }.dialog-actions button { padding: 9px 13px; border-radius: 8px; color: #697991; background: #f1f4f8; }.dialog-actions .primary { color: #fff; background: #2e67dc; }.dialog-actions .delete-folder { color: #bd4545; background: #fff1f1; }
.favorite-toast { position: fixed; left: 50%; bottom: 28px; z-index: 600; transform: translateX(-50%); padding: 10px 17px; border-radius: 9px; color: #fff; background: rgba(22, 34, 55, .92); font-size: 12px; }
@media (max-width: 900px) { .favorite-grid { grid-template-columns: 1fr; }.favorite-toolbar { grid-template-columns: 1fr 1fr; }.search-box { grid-column: 1 / -1; } }
@media (max-width: 600px) { .favorites-hero { align-items: flex-start; flex-direction: column; }.hero-count { text-align: left; }.favorite-toolbar { grid-template-columns: 1fr; }.search-box { grid-column: auto; }.card-actions { flex-wrap: wrap; justify-content: flex-end; } }
</style>
