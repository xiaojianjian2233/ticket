<script setup>
// 轻量 ECharts 封装：传 option 即渲染，自适应 resize，卸载销毁。
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '300px' },
})
const el = ref(null)
let chart = null

const render = () => {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  chart.setOption(props.option, true)
}
const onResize = () => chart && chart.resize()

onMounted(() => { render(); window.addEventListener('resize', onResize) })
watch(() => props.option, render, { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', onResize); chart && chart.dispose(); chart = null })
</script>

<template>
  <div ref="el" :style="{ width: '100%', height }"></div>
</template>
