<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Collection, Cpu, Share, DataAnalysis, Key } from '@element-plus/icons-vue';
import { useUserStore } from '@/stores/user';
import { getApiKeyStatus, type UserApiKeyStatus } from '@/api/apiKeys';

const router = useRouter();
const userStore = useUserStore();
const apiKeyStatus = ref<UserApiKeyStatus | null>(null);

const welcomeText = computed(() => {
  const name = userStore.userInfo?.username || '用户';
  return `欢迎回来，${name}`;
});

const needsApiKeySetup = computed(
  () => apiKeyStatus.value !== null && !apiKeyStatus.value.has_llm_key,
);

async function fetchApiKeyStatus(): Promise<void> {
  try {
    apiKeyStatus.value = await getApiKeyStatus();
  } catch (error) {
    console.error('[Fetch API Key Status Error]', error);
  }
}

function goToApiKeys(): void {
  router.push('/settings/api-keys');
}

onMounted(fetchApiKeyStatus);

/** 功能模块概览卡片 */
const statCards = [
  {
    title: '知识库',
    value: '0',
    unit: '个',
    description: '企业私有知识沉淀',
    icon: Collection,
  },
  {
    title: '智能体',
    value: '0',
    unit: '个',
    description: '单 Agent 任务自动化',
    icon: Cpu,
  },
  {
    title: '工作流',
    value: '0',
    unit: '个',
    description: 'LangGraph 多智能体编排',
    icon: Share,
  },
  {
    title: '今日对话',
    value: '0',
    unit: '次',
    description: '流式交互会话统计',
    icon: DataAnalysis,
  },
];
</script>

<template>
  <div class="dashboard-page">
    <el-alert
      v-if="needsApiKeySetup"
      type="info"
      show-icon
      :closable="false"
      class="api-key-guide"
      title="开始使用前，请先配置 API 密钥"
    >
      <template #default>
        <p class="guide-text">
          系统不再使用全局 API 密钥。请在「API 密钥管理」中配置您的大模型密钥，以启用知识库、智能体与工作流功能。
        </p>
        <el-button type="primary" :icon="Key" @click="goToApiKeys">前往配置</el-button>
      </template>
    </el-alert>

    <el-card class="welcome-card" shadow="never">
      <div class="welcome-content">
        <h2 class="welcome-title">{{ welcomeText }}</h2>
        <p class="welcome-desc">
          企业智能协作工作台已就绪，后续将在此接入知识库问答、智能体对话与工作流编排能力。
        </p>
      </div>
    </el-card>

    <el-row :gutter="20" class="stat-row">
      <el-col v-for="card in statCards" :key="card.title" :xs="24" :sm="12" :lg="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-card-body flex-between">
            <div class="stat-info">
              <p class="stat-title">{{ card.title }}</p>
              <p class="stat-value">
                {{ card.value }}
                <span class="stat-unit">{{ card.unit }}</span>
              </p>
              <p class="stat-desc">{{ card.description }}</p>
            </div>
            <div class="stat-icon">
              <el-icon :size="24"><component :is="card.icon" /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-row">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <template #header>
            <span class="card-header-title">平台能力概览</span>
          </template>
          <el-timeline>
            <el-timeline-item timestamp="增强 RAG" placement="top" type="primary">
              7 层全链路优化：文档接入、智能分块、双路检索、重排序、引用溯源
            </el-timeline-item>
            <el-timeline-item timestamp="单 Agent" placement="top" type="success">
              工具调用、任务规划、流式对话，支持多模型切换与降级兜底
            </el-timeline-item>
            <el-timeline-item timestamp="LangGraph" placement="top" type="warning">
              多智能体串行 / 并行 / 分支工作流编排，支持人工介入与状态追踪
            </el-timeline-item>
            <el-timeline-item timestamp="工程化" placement="top" type="info">
              SSE 流式输出、Pinia 状态管理、权限路由、容器化部署
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>
            <span class="card-header-title">快速开始</span>
          </template>
          <el-steps direction="vertical" :active="1">
            <el-step title="项目脚手架" description="前后端基础框架已搭建" />
            <el-step title="用户体系" description="登录认证与 RBAC 权限" />
            <el-step title="知识库" description="文档上传与增强 RAG 检索" />
            <el-step title="智能体 & 工作流" description="Agent 对话与 LangGraph 编排" />
          </el-steps>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style lang="scss" scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 20px;

  .api-key-guide {
    margin-bottom: 0;
  }

  .guide-text {
    margin: 0 0 8px;
    line-height: 1.5;
  }
}

.welcome-card {
  background: $bg-white;
  border: 1px solid $border-color;

  :deep(.el-card__body) {
    padding: 28px 32px;
  }
}

.welcome-title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
}

.welcome-desc {
  margin: 0;
  font-size: 14px;
  color: $text-secondary;
  line-height: 1.6;
}

.stat-row {
  margin-top: 0;
}

.stat-card {
  margin-bottom: 0;
}

.stat-card-body {
  gap: 16px;
}

.stat-title {
  margin: 0 0 4px;
  font-size: 14px;
  color: $text-secondary;
}

.stat-value {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: $text-primary;
}

.stat-unit {
  font-size: 14px;
  font-weight: 400;
  color: $text-secondary;
}

.stat-desc {
  margin: 8px 0 0;
  font-size: 12px;
  color: $text-secondary;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border: 1px solid $border-color;
  border-radius: $border-radius;
  flex-shrink: 0;
  color: $primary-color;
  background: rgba($primary-color, 0.06);
}

.content-row {
  margin-top: 0;
}

.card-header-title {
  font-size: 16px;
  font-weight: 500;
  color: $text-primary;
}
</style>
