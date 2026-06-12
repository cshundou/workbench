<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
  CanvasRenderer,
]);

const props = withDefaults(
  defineProps<{
    config: Record<string, unknown>;
    title?: string;
    height?: number;
    showToolbar?: boolean;
  }>(),
  {
    height: 280,
    showToolbar: true,
  },
);

const emit = defineEmits<{
  enlarge: [];
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

/** 将简化配置转为 ECharts option */
function buildOption(config: Record<string, unknown>): EChartsOption | null {
  if (config.series || config.xAxis) {
    return config as EChartsOption;
  }

  const chartType = String(config.type || 'bar');
  const summary = String(config.summary || '数据分析');
  const labels = (config.labels as string[]) || ['指标A', '指标B', '指标C', '指标D'];
  const values = (config.values as number[]) || [42, 68, 35, 91];
  const tableData = config.data as { columns?: string[]; rows?: string[][] } | undefined;

  if (chartType === 'table' && tableData?.columns && tableData?.rows) {
    return null;
  }

  const baseOption: EChartsOption = {
    title: { text: props.title || summary.slice(0, 40), left: 'center', textStyle: { fontSize: 13 } },
    tooltip: { trigger: chartType === 'pie' ? 'item' : 'axis' },
    legend: { bottom: 0 },
    grid: { left: 48, right: 24, top: 48, bottom: 48 },
    color: ['#ff5a1f', '#ff8a5c', '#ffb088', '#ffd4b8'],
  };

  if (chartType === 'pie') {
    return {
      ...baseOption,
      series: [
        {
          type: 'pie',
          radius: ['35%', '65%'],
          data: labels.map((name, i) => ({ name, value: values[i] ?? 0 })),
        },
      ],
    };
  }

  if (chartType === 'line') {
    return {
      ...baseOption,
      xAxis: { type: 'category', data: labels },
      yAxis: { type: 'value' },
      series: [{ type: 'line', smooth: true, data: values, areaStyle: { opacity: 0.08 } }],
    };
  }

  return {
    ...baseOption,
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: values, barMaxWidth: 48 }],
  };
}

const isTable = computed(() => {
  const config = props.config;
  if (config.type === 'table') return true;
  const data = config.data as { columns?: string[]; rows?: string[][] } | undefined;
  return Boolean(data?.columns && data?.rows);
});

const tableData = computed(() => {
  const data = props.config.data as { columns?: string[]; rows?: string[][] } | undefined;
  return {
    columns: data?.columns || [],
    rows: data?.rows || [],
  };
});

function renderChart(): void {
  if (!chartRef.value || isTable.value) return;
  const option = buildOption(props.config);
  if (!option) return;

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }
  chartInstance.setOption(option, true);
}

function handleResize(): void {
  chartInstance?.resize();
}

async function exportImage(): Promise<void> {
  if (!chartInstance) return;
  try {
    const url = chartInstance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' });
    const link = document.createElement('a');
    link.href = url;
    link.download = `${props.title || 'chart'}.png`;
    link.click();
    ElMessage.success('图表已导出');
  } catch {
    ElMessage.error('导出失败');
  }
}

function exportTableCsv(): void {
  const { columns, rows } = tableData.value;
  const lines = [columns.join(','), ...rows.map((r) => r.join(','))];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${props.title || 'data'}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  ElMessage.success('数据已导出');
}

watch(
  () => props.config,
  () => {
    renderChart();
  },
  { deep: true },
);

onMounted(() => {
  renderChart();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
  chartInstance = null;
});
</script>

<template>
  <div class="chart-renderer">
    <div v-if="showToolbar" class="chart-toolbar">
      <span class="chart-title">{{ title || '数据图表' }}</span>
      <div class="chart-actions">
        <button v-if="!isTable" type="button" class="chart-btn" @click="exportImage">导出图片</button>
        <button v-if="isTable" type="button" class="chart-btn" @click="exportTableCsv">
          导出数据
        </button>
        <button type="button" class="chart-btn" @click="emit('enlarge')">放大查看</button>
      </div>
    </div>

    <div v-if="isTable" class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="col in tableData.columns" :key="col">{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, ri) in tableData.rows" :key="ri">
            <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else ref="chartRef" class="chart-canvas" :style="{ height: `${height}px` }" />
  </div>
</template>

<style lang="scss" scoped>
.chart-renderer {
  margin-top: 10px;
  border: 1px solid $border-color;
  border-radius: 8px;
  overflow: hidden;
  background: $bg-white;
}

.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid $border-color;
}

.chart-title {
  font-size: 13px;
  font-weight: 500;
  color: $text-primary;
}

.chart-actions {
  display: flex;
  gap: 8px;
}

.chart-btn {
  padding: 2px 8px;
  font-size: 12px;
  color: $primary-color;
  background: transparent;
  border: 1px solid rgba($primary-color, 0.4);
  border-radius: 4px;
  cursor: pointer;

  &:hover {
    background: rgba($primary-color, 0.06);
  }
}

.chart-canvas {
  width: 100%;
}

.data-table-wrap {
  overflow-x: auto;
  padding: 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;

  th,
  td {
    border: 1px solid $border-color;
    padding: 8px 12px;
    text-align: left;
  }

  th {
    background: #fafafa;
    font-weight: 600;
  }

  tr:nth-child(even) td {
    background: #fafbfc;
  }
}
</style>
