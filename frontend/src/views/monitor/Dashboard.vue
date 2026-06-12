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
  exportTokenUsage,
  getAlertConfig,
  getAlertHistory,
  getUserActivity,
  getToolStats,
  getWorkflowStats,
  getGroupChatStats,
  type AlertConfig,
  type GroupChatStats,
  type AlertHistoryItem,
  type ApiStats,
  type ErrorLogItem,
  type SystemHealth,
  type TokenUsageStats,
  type ToolStats,
  type UserActivityStats,
  type WorkflowStats,
} from '@/api/monitor';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import BentoCard from '@/components/layout/BentoCard.vue';

const loading = ref(false);
const tokenGroupBy = ref<'day' | 'user' | 'model'>('day');
const statsDays = ref(7);

const tokenStats = ref<TokenUsageStats | null>(null);
const apiStats = ref<ApiStats | null>(null);
const toolStats = ref<ToolStats | null>(null);
const workflowStats = ref<WorkflowStats | null>(null);
const groupChatStats = ref<GroupChatStats | null>(null);
const errorLogs = ref<ErrorLogItem[]>([]);
const health = ref<SystemHealth | null>(null);
const userActivity = ref<UserActivityStats | null>(null);
const alertConfig = ref<AlertConfig | null>(null);
const alertHistory = ref<AlertHistoryItem[]>([]);
const exportLoading = ref(false);
const tokenChartRef = ref<HTMLDivElement | null>(null);
const modelChartRef = ref<HTMLDivElement | null>(null);
const apiChartRef = ref<HTMLDivElement | null>(null);
const toolChartRef = ref<HTMLDivElement | null>(null);

let tokenChart: echarts.ECharts | null = null;
let modelChart: echarts.ECharts | null = null;
let apiChart: echarts.ECharts | null = null;
let toolChart: echarts.ECharts | null = null;

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
  {
    title: '接口成功率',
    value: ((apiStats.value?.summary.success_rate ?? 1) * 100).toFixed(1),
    unit: '%',
    color: '#00B42A',
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

function buildToolChartOption(data: ToolStats): EChartsOption {
  const series = data.daily_series;
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const items = params as { axisValue: string; seriesName: string; value: number }[];
        const date = items[0]?.axisValue ?? '';
        const rateItem = items.find((item) => item.seriesName === '成功率');
        const rate = rateItem ? (rateItem.value * 100).toFixed(1) : '100.0';
        return `${date}<br/>工具调用成功率：${rate}%`;
      },
    },
    grid: { left: 48, right: 24, bottom: 48, top: 40 },
    xAxis: {
      type: 'category',
      data: series.map((item) => item.date),
    },
    yAxis: {
      type: 'value',
      name: '成功率',
      min: 0,
      max: 1,
      axisLabel: { formatter: (value: number) => `${(value * 100).toFixed(0)}%` },
    },
    series: [
      {
        name: '成功率',
        type: 'line',
        smooth: true,
        data: series.map((item) => item.success_rate),
        itemStyle: { color: '#165DFF' },
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
  if (toolStats.value && toolChart) {
    toolChart.setOption(buildToolChartOption(toolStats.value), true);
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
    const [
      tokenData,
      apiData,
      toolData,
      workflowData,
      groupChatData,
      errorData,
      healthData,
      activityData,
      alertCfg,
      alerts,
    ] = await Promise.all([
      getTokenUsage({ group_by: tokenGroupBy.value }),
      getApiStats(statsDays.value),
      getToolStats(statsDays.value),
      getWorkflowStats(statsDays.value),
      getGroupChatStats(statsDays.value),
      getErrorLogs({ page: 1, page_size: 10 }),
      getMonitorHealth(),
      getUserActivity(),
      getAlertConfig(),
      getAlertHistory(10),
    ]);
    tokenStats.value = tokenData;
    apiStats.value = apiData;
    toolStats.value = toolData;
    workflowStats.value = workflowData;
    groupChatStats.value = groupChatData;
    errorLogs.value = errorData.items;
    health.value = healthData;
    userActivity.value = activityData;
    alertConfig.value = alertCfg;
    alertHistory.value = alerts.items;
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
  toolChart?.resize();
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

async function handleExportToken(format: 'csv' | 'excel'): Promise<void> {
  exportLoading.value = true;
  try {
    await exportTokenUsage(format, { group_by: tokenGroupBy.value });
    ElMessage.success('导出成功');
  } catch (error) {
    console.error('[Token Export]', error);
    ElMessage.error('导出失败');
  } finally {
    exportLoading.value = false;
  }
}

watch(tokenGroupBy, () => {
  void fetchDashboardData();
});

onMounted(() => {
  tokenChart = initChart(tokenChartRef.value);
  modelChart = initChart(modelChartRef.value);
  apiChart = initChart(apiChartRef.value);
  toolChart = initChart(toolChartRef.value);
  window.addEventListener('resize', handleResize);
  void fetchDashboardData();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  tokenChart?.dispose();
  modelChart?.dispose();
  apiChart?.dispose();
  toolChart?.dispose();
});
</script>

<template>
  <div v-loading="loading" class="monitor-dashboard">
    <SectionHeader title="监控面板" description="Token 消耗、API 调用量与系统健康状态实时监控" />

    <el-row :gutter="20" class="summary-row">
      <el-col v-for="card in summaryCards" :key="card.title" :xs="24" :sm="12" :lg="6">
        <BentoCard
          :title="card.title"
          :value="String(card.value)"
          :unit="card.unit"
          class="summary-card"
        />
      </el-col>
    </el-row>

    <el-row v-if="userActivity" :gutter="20" class="summary-row">
      <el-col :xs="24" :sm="8">
        <BentoCard title="DAU" :value="String(userActivity.dau)" unit="人" />
      </el-col>
      <el-col :xs="24" :sm="8">
        <BentoCard title="WAU" :value="String(userActivity.wau)" unit="人" />
      </el-col>
      <el-col :xs="24" :sm="8">
        <BentoCard title="MAU" :value="String(userActivity.mau)" unit="人" />
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header flex-between">
              <span>Token 消耗趋势</span>
              <div class="card-actions">
                <el-radio-group v-model="tokenGroupBy" size="small">
                  <el-radio-button value="day">按时间</el-radio-button>
                  <el-radio-button value="user">按用户</el-radio-button>
                  <el-radio-button value="model">按模型</el-radio-button>
                </el-radio-group>
                <el-button size="small" :loading="exportLoading" @click="handleExportToken('csv')">
                  导出 CSV
                </el-button>
                <el-button
                  size="small"
                  :loading="exportLoading"
                  @click="handleExportToken('excel')"
                >
                  导出 Excel
                </el-button>
              </div>
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

    <el-row v-if="workflowStats" :gutter="20" class="mb-4">
      <el-col :xs="24" :sm="8">
        <BentoCard title="工作流执行次数" :value="String(workflowStats.total_count)" />
      </el-col>
      <el-col :xs="24" :sm="8">
        <BentoCard
          title="平均耗时 (ms)"
          :value="String(Math.round(workflowStats.avg_duration_ms))"
        />
      </el-col>
      <el-col :xs="24" :sm="8">
        <BentoCard
          title="失败率"
          :value="`${(workflowStats.failure_rate * 100).toFixed(1)}%`"
        />
      </el-col>
    </el-row>

    <el-row v-if="groupChatStats" :gutter="20" class="mb-4">
      <el-col :xs="24" :sm="6">
        <BentoCard title="群聊会话数" :value="String(groupChatStats.session_count)" />
      </el-col>
      <el-col :xs="24" :sm="6">
        <BentoCard
          title="群聊平均时长 (ms)"
          :value="String(Math.round(groupChatStats.avg_duration_ms))"
        />
      </el-col>
      <el-col :xs="24" :sm="6">
        <BentoCard
          title="审核通过率"
          :value="`${(groupChatStats.review_pass_rate * 100).toFixed(1)}%`"
        />
      </el-col>
      <el-col :xs="24" :sm="6">
        <BentoCard
          title="审核打回次数"
          :value="String(groupChatStats.total_review_retries)"
        />
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header flex-between">
              <span>工具调用成功率</span>
              <el-tag v-if="toolStats" type="success" size="small">
                当前 {{ ((toolStats.summary.success_rate ?? 1) * 100).toFixed(1) }}%
              </el-tag>
            </div>
          </template>
          <div ref="toolChartRef" class="chart-container" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header flex-between">
              <span>API 调用统计</span>
              <el-select
                v-model="statsDays"
                size="small"
                style="width: 120px"
                @change="fetchDashboardData"
              >
                <el-option :value="7" label="近 7 天" />
                <el-option :value="14" label="近 14 天" />
                <el-option :value="30" label="近 30 天" />
              </el-select>
            </div>
          </template>
          <div ref="apiChartRef" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="10">
        <el-card v-if="alertConfig" shadow="never" class="alert-card">
          <template #header>
            <span>监控告警</span>
          </template>
          <div class="alert-config">
            <p>状态：{{ alertConfig.enabled ? '已启用' : '未启用' }}</p>
            <p>慢接口阈值：{{ alertConfig.slow_api_threshold_ms }} ms</p>
            <p>错误率阈值：{{ (alertConfig.error_rate_threshold * 100).toFixed(1) }}%</p>
            <p>
              通知渠道：
              <el-tag v-if="alertConfig.email_configured" size="small" type="success">邮件</el-tag>
              <el-tag v-if="alertConfig.dingtalk_configured" size="small" type="success"
                >钉钉</el-tag
              >
              <span v-if="!alertConfig.email_configured && !alertConfig.dingtalk_configured">
                未配置
              </span>
            </p>
          </div>
          <el-table :data="alertHistory" stripe size="small" max-height="180">
            <el-table-column prop="timestamp" label="时间" width="170" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="message" label="消息" min-width="160" show-overflow-tooltip />
          </el-table>
        </el-card>

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
  margin-bottom: 20px;
}

.card-header {
  width: 100%;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.alert-card {
  margin-bottom: 20px;
}

.alert-config {
  font-size: 13px;
  color: $text-secondary;
  margin-bottom: 12px;

  p {
    margin: 4px 0;
  }
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
