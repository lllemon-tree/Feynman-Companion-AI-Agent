<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 20 }
})

const paths = {
  book: ['M4 19.5A2.5 2.5 0 0 1 6.5 17H20', 'M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z'],
  chat: ['M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z'],
  layers: ['M12 2 3 7l9 5 9-5-9-5Z', 'm3 12 9 5 9-5', 'm3 17 9 5 9-5'],
  calendar: ['M8 2v4', 'M16 2v4', 'M3 10h18', 'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z'],
  chart: ['M3 3v18h18', 'M7 16v-4', 'M12 16V8', 'M17 16V5'],
  plus: ['M12 5v14', 'M5 12h14'],
  chevron: ['m9 18 6-6-6-6'],
  down: ['m6 9 6 6 6-6'],
  send: ['m22 2-7 20-4-9-9-4 20-7Z', 'M22 2 11 13'],
  menu: ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  close: ['M18 6 6 18', 'm6 6 12 12'],
  sparkles: ['m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z', 'm19 16 .7 1.3L21 18l-1.3.7L19 20l-.7-1.3L17 18l1.3-.7L19 16Z'],
  graduate: ['m2 10 10-6 10 6-10 6-10-6Z', 'M6 12.5V17c3.5 3 8.5 3 12 0v-4.5', 'M22 10v6'],
  user: ['M20 21a8 8 0 0 0-16 0', 'M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z'],
  logout: ['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4', 'M16 17l5-5-5-5', 'M21 12H9']
}

const iconPaths = computed(() => paths[props.name] || paths.chat)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="path in iconPaths" :key="path" :d="path" />
  </svg>
</template>
