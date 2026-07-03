<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  dimensions: {
    type: Array,
    required: true
  }
})

const chartEl = ref(null)
const tooltipVisible = ref(false)
const tooltipContent = ref('')
const tooltipX = ref(0)
const tooltipY = ref(0)
let chartInstance = null

function buildOption() {
  const indicators = props.dimensions.map((dim) => ({
    name: dim.name.length > 3 ? dim.name.slice(0, 2) + '\n' + dim.name.slice(2) : dim.name,
    max: 10
  }))
  const values = props.dimensions.map((dim) => dim.score ?? 0)
  return {
    tooltip: {
      show: false
    },
    padding: [20, 25, 20, 25],
    radar: {
      indicator: indicators,
      center: ['50%', '50%'],
      radius: '48%',
      splitNumber: 5,
      axisName: {
        color: '#5a6072',
        fontSize: 10,
        interval: 0,
        margin: 18,
        textAlign: 'center',
        lineHeight: 15
      },
      splitLine: { lineStyle: { color: '#e6e8ee' } },
      splitArea: { areaStyle: { color: ['#fafbfd', '#ffffff'] } },
      axisLine: { lineStyle: { color: '#e6e8ee' } }
    },
    series: [
      {
        type: 'radar',
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#4f6bff', width: 2 },
        itemStyle: { color: '#4f6bff' },
        areaStyle: { color: 'rgba(79, 107, 255, 0.18)' },
        emphasis: {
          itemStyle: { color: '#4f6bff' },
          lineStyle: { color: '#4f6bff', width: 3 }
        },
        data: [{ value: values, name: '本次得分' }]
      }
    ]
  }
}

function render() {
  if (!chartInstance) return
  chartInstance.setOption(buildOption(), true)
}

function showTooltip(index, event) {
  const dim = props.dimensions[index]
  if (!dim) return
  tooltipContent.value = `${dim.name}<br/>得分: ${dim.score}/10`
  
  const rect = chartEl.value.getBoundingClientRect()
  tooltipX.value = event.offsetX
  tooltipY.value = event.offsetY
  tooltipVisible.value = true
}

function hideTooltip() {
  tooltipVisible.value = false
}

onMounted(() => {
  chartInstance = echarts.init(chartEl.value)
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = null
})

watch(() => props.dimensions, render, { deep: true })

function resize() {
  chartInstance?.resize()
}
</script>

<template>
  <div class="radar-wrapper">
    <div ref="chartEl" class="radar-chart" />
    
    <div class="radar-overlay">
      <div 
        class="quadrant quadrant-top" 
        @mouseenter="(e) => showTooltip(0, e)" 
        @mouseleave="hideTooltip"
      />
      <div 
        class="quadrant quadrant-right" 
        @mouseenter="(e) => showTooltip(3, e)" 
        @mouseleave="hideTooltip"
      />
      <div 
        class="quadrant quadrant-bottom" 
        @mouseenter="(e) => showTooltip(2, e)" 
        @mouseleave="hideTooltip"
      />
      <div 
        class="quadrant quadrant-left" 
        @mouseenter="(e) => showTooltip(1, e)" 
        @mouseleave="hideTooltip"
      />
    </div>
    
    <div 
      v-if="tooltipVisible" 
      class="radar-tooltip"
      :style="{ left: tooltipX + 'px', top: tooltipY + 'px' }"
      v-html="tooltipContent"
    />
  </div>
</template>

<style scoped>
.radar-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.radar-chart {
  width: 100%;
  height: 100%;
}

.radar-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.quadrant {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
}

.quadrant-top {
  clip-path: polygon(50% 50%, 0% 0%, 100% 0%);
}

.quadrant-right {
  clip-path: polygon(50% 50%, 100% 0%, 100% 100%);
}

.quadrant-bottom {
  clip-path: polygon(50% 50%, 100% 100%, 0% 100%);
}

.quadrant-left {
  clip-path: polygon(50% 50%, 0% 100%, 0% 0%);
}

.radar-tooltip {
  position: absolute;
  background: #fff;
  border: 1px solid #e6e8ee;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12px;
  color: #1A1D23;
  line-height: 18px;
  pointer-events: none;
  transform: translate(-50%, -120%);
  white-space: nowrap;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
</style>