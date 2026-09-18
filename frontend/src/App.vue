<script setup>
import { ref } from 'vue'
import { RouterView } from 'vue-router'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const sidebar = ref(null)
</script>

<template>
  <RouterView v-if="route.meta.public" />
  <div v-else class="app-layout">
    <AppSidebar ref="sidebar" />
    <div class="app-workspace">
      <button class="mobile-nav-trigger" type="button" aria-label="打开导航菜单" @click="sidebar?.openMenu()">
        <AppIcon name="menu" :size="20" /><span>费曼伴学</span>
      </button>
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
.app-layout { display: flex; width: 100%; height: 100dvh; background: #fff; }
.app-workspace { min-width: 0; min-height: 0; flex: 1; height: 100dvh; overflow-y: auto; display: flex; flex-direction: column; background: #F8FAFC; }
.mobile-nav-trigger { display: none; }
@media (max-width: 760px) {
  .mobile-nav-trigger { position: sticky; top: 0; z-index: 18; display: flex; align-items: center; gap: 9px; width: 100%; min-height: 44px; padding: 0 17px; color: #245bd4; background: #fff; border-bottom: 1px solid #e9eef6; font-size: 13px; font-weight: 650; text-align: left; }
}
</style>
