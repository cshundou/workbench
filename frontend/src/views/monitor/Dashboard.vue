<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import { ElMessage } from 'element-plus';
import {
  getApiStats,
  getErrorLogs,
  getMonitorHealth,
  getTokenUsage,
  type ApiStats,
  type ErrorLogItem,
  type SystemHealth,
  type TokenUsageStats,
} from '@/api/monitor';

const loading = ref(false);
const tokenGroupBy = ref<'day' | 'user' | 'model'>('day');
const statsDays = ref(7);

const tokenStats = ref<TokenUsageStats | null>(null);
const apiStats = ref<ApiStats | null>(null);
const errorLogs = ref<ErrorLogItem[]>([]);
const health = ref<SystemHealth | null>(null);

const tokenChartRef = ref<HTMLDivElement | null>(null);
const modelChartRef = ref<HTMLDivElement | null>(null);
const apiChartRef = ref<HTMLDivElement | null>(null);

let tokenChart: echarts.ECharts | null = null;
let modelChart: echarts.ECharts | null = null;
let apiChart: echarts.ECharts | null = null;

const summaryCards = computed(() => [
  {
    title: 'Token 总消耗',
    value: tokenStats.value?.summary.total_tokens ?? 0,
    unit: 'tokens',
    color: '#FF5A1F',
  },
  {
    title: 'API 调用量',
    value: apiStats.value?.summary.total_count ?? 0,
    unit: '次',
    color: '#1D2129',
  },
  {
    title: '平均响应时间',
    value: apiStats.value?.summary.avg_response_ms ?? 0,
    unit: 'ms',
    color: '#4E5969',
  },
  {
    title: '错误请求',
    value: apiStats.value?.summary.error_count ?? 0,
    unit: '次',
    color: '#F53F3F',
  },
]);

function initChart(el: HTMLDivElement | null): echarts.ECharts | null {
  if (!el) {
    return null;
  }
  return echarts.init(el);
}

function buildTokenChartOption(data: TokenUsageStats): EChartsOption {
  const breakdown = data.breakdown;

  if (tokenGroupBy.value === 'model') {
    const items = breakdown as { model_name: string; total_tokens: number }[];
    return {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [
        {
          type: 'pie',
          radius: ['40%', '68%'],
          data: items.map((item) => ({
            name: item.model_name,
            value: item.total_tokens,
          })),
        },
      ],
    };
  }

  if (tokenGroupBy.value === 'user') {
    const items = breakdown as { username: string; total_tokens: number }[];
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 48, right: 24, bottom: 48, top: 24 },
      xAxis: {
        type: 'category',
        data: items.map((item) => item.username),
        axisLabel: { rotate: 30 },
      },
      yAxis: {
        type: 'value',
        name: 'Tokens',
        splitLine: { show: false },
        axisLine: { lineStyle: { color: '#E5E6EB' } },
        axisLabel: { color: '#86909C' },
      },
      series: [
        {
          type: 'bar',
          data: items.map((item) => item.total_tokens),
          itemStyle: { color: '#FF5A1F' },
        },
      ],
    };
  }

  const items = breakdown as { date: string; total_tokens: number }[];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, bottom: 48, top: 24 },
    xAxis: {
      type: 'category',
      data: items.map((item) => item.date),
      axisLine: { lineStyle: { color: '#E5E6EB' } },
      axisTick: { show: false },
      axisLabel: { color: '#86909C' },
    },
    yAxis: { type: 'value', name: 'Tokens' },
    series: [
      {
        type: 'line',
        smooth: true,
        data: items.map((item) => item.total_tokens),
        itemStyle: { color: '#FF5A1F' },
        lineStyle: { width: 2 },
      },
    ],
  };
}

function buildModelPieOption(data: TokenUsageStats): EChartsOption {
  const items = (data.breakdown as { model_name: string; total_tokens: number }[]).length
    ? (data.breakdown as { model_name: string; total_tokens: number }[])
    : [];

  if (tokenGroupBy.value !== 'model' && items.length === 0) {
    return {
      title: {
        text: '暂无模型分布数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#909399', fontSize: 14, fontWeight: 400 },
      },
    };
  }

  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: '62%',
        data: items.map((item) => ({
          name: item.model_name,
          value: item.total_tokens,
        })),
      },
    ],
  };
}

function buildApiChartOption(data: ApiStats): EChartsOption {
  const series = data.daily_series;
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['调用量', '平均响应(ms)'] },
    grid: { left: 48, right: 48, bottom: 48, top: 40 },
    xAxis: {
      type: 'category',
      data: series.map((item) => item.date),
    },
    yAxis: [
      { type: 'value', name: '次数', splitLine: { show: false }, axisLabel: { color: '#86909C' } },
      { type: 'value', name: 'ms', splitLine: { show: false }, axisLabel: { color: '#86909C' } },
    ],
    series: [
      {
        name: '调用量',
        type: 'bar',
        data: series.map((item) => item.count),
        itemStyle: { color: '#00B42A' },
      },
      {
        name: '平均响应(ms)',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: series.map((item) => item.avg_response_ms),
        itemStyle: { color: '#FF7D00' },
      },
    ],
  };
}

function renderCharts(): void {
  if (tokenStats.value && tokenChart) {
    tokenChart.setOption(buildTokenChartOption(tokenStats.value), true);
  }
  if (apiStats.value && apiChart) {
    apiChart.setOption(buildApiChartOption(apiStats.value), true);
  }
}

async function loadModelBreakdown(): Promise<void> {
  if (tokenGroupBy.value === 'model') {
    return;
  }
  const modelData = await getTokenUsage({ group_by: 'model' });
  if (modelChart) {
    modelChart.setOption(buildModelPieOption(modelData), true);
  }
}

async function fetchDashboardData(): Promise<void> {
  loading.value = true;
  try {
    const [tokenData, apiData, errorData, healthData] = await Promise.all([
      getTokenUsage({ group_by: tokenGroupBy.value }),
      getApiStats(statsDays.value),
      getErrorLogs({ page: 1, page_size: 10 }),
      getMonitorHealth(),
    ]);
    tokenStats.value = tokenData;
    apiStats.value = apiData;
    errorLogs.value = errorData.items;
    health.value = healthData;
    renderCharts();
    await loadModelBreakdown();
  } catch (error) {
    console.error('[Monitor Dashboard]', error);
    ElMessage.error('加载监控数据失败');
  } finally {
    loading.value = false;
  }
}

function handleResize(): void {
  tokenChart?.resize();
  modelChart?.resize();
  apiChart?.resize();
}

function healthTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'healthy') {
    return 'success';
  }
  if (status === 'degraded') {
    return 'warning';
  }
  return 'danger';
}

watch(tokenGroupBy, () => {
  void fetchDashboardData();
});

onMounted(() => {
  tokenChart = initChart(tokenChartRef.value);
  modelChart = initChart(modelChartRef.value);
  apiChart = initChart(apiChartRef.value);
  window.addEventListener('resize', handleResize);
  void fetchDashboardData();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  tokenChart?.dispose();
  modelChart?.dispose();
  apiChart?.dispose();
});
</script>

<template>
  <div v-loading="loading" class="monitor-dashboard">
    <el-row :gutter="20" class="summary-row">
      <el-col v-for="card in summaryCards" :key="card.title" :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="summary-card">
          <p class="summary-title">{{ card.title }}</p>
          <p class="summary-value" :style="{ color: card.color }">
            {{ card.value }}
            <span class="summary-unit">{{ card.unit }}</span>
          </p>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header flex-between">
              <span>Token 消耗趋势</span>
              <el-radio-group v-model="tokenGroupBy" size="small">
                <el-radio-button value="day">按时间</el-radio-button>
                <el-radio-button value="user">按用户</el-radio-button>
                <el-radio-button value="model">按模型</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="tokenChartRef" class="chart-container" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>
            <span>系统健康状态</span>
          </template>
          <div v-if="health" class="health-list">
            <div class="health-overall flex-between">
              <span>整体状态</span>
              <el-tag :type="healthTagType(health.status)">{{ health.status }}</el-tag>
            </div>
            <div
              v-for="(component, name) in health.components"
              :key="name"
              class="health-item flex-between"
            >
              <span>{{ name }}</span>
              <el-tag :type="healthTagType(component.status)" size="small">
                {{ component.status }}
              </el-tag>
            </div>
            <p class="health-time">更新时间：{{ health.timestamp }}</p>
          </div>
        </el-card>

        <el-card shadow="never" class="model-card">
          <template #header>
            <span>模型 Token 分布</span>
          </template>
          <div ref="modelChartRef" class="chart-container chart-container-sm" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-header flex-between">
              <span>API 调用统计</span>
              <el-select v-model="statsDays" size="small" style="width: 120px" @change="fetchDashboardData">
                <el-option :value="7" label="近 7 天" />
                <el-option :value="14" label="近 14 天" />
                <el-option :value="30" label="近 30 天" />
              </el-select>
            </div>
          </template>
          <div ref="apiChartRef" class="chart-container" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never">
          <template #header>
            <span>最近错误日志</span>
          </template>
          <el-table :data="errorLogs" stripe size="small" max-height="360">
            <el-table-column prop="timestamp" label="时间" width="170" />
            <el-table-column prop="status_code" label="状态码" width="80" />
            <el-table-column prop="path" label="路径" min-width="140" show-overflow-tooltip />
            <el-table-column prop="message" label="消息" min-width="120" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style lang="scss" scoped>
.monitor-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.summary-card {
  margin-bottom: 0;
}

.summary-title {
  margin: 0 0 8px;
  font-size: 14px;
  color: $text-secondary;
}

.summary-value {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
}

.summary-unit {
  margin-left: 4px;
  font-size: 14px;
  font-weight: 400;
  color: $text-secondary;
}

.card-header {
  width: 100%;
}

.chart-container {
  width: 100%;
  height: 320px;
}

.chart-container-sm {
  height: 240px;
}

.model-card {
  margin-top: 20px;
}

.health-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.health-overall {
  font-weight: 500;
  padding-bottom: 8px;
  border-bottom: 1px solid $border-color;
}

.health-item {
  font-size: 14px;
}

.health-time {
  margin: 8px 0 0;
  font-size: 12px;
  color: $text-secondary;
}
</style>
