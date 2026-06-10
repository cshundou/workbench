<script setup lang="ts">
import { computed } from 'vue';
import { Collection, Cpu, Share, DataAnalysis } from '@element-plus/icons-vue';
import { useUserStore } from '@/stores/user';

const userStore = useUserStore();

const welcomeText = computed(() => {
  const name = userStore.userInfo?.username || '用户';
  return `欢迎回来，${name}`;
});

/** 功能模块概览卡片 */
const statCards = [
  {
    title: '知识库',
    value: '0',
    unit: '个',
    description: '企业私有知识沉淀',
    icon: Collection,
    color: '#409eff',
  },
  {
    title: '智能体',
    value: '0',
    unit: '个',
    description: '单 Agent 任务自动化',
    icon: Cpu,
    color: '#67c23a',
  },
  {
    title: '工作流',
    value: '0',
    unit: '个',
    description: 'LangGraph 多智能体编排',
    icon: Share,
    color: '#e6a23c',
  },
  {
    title: '今日对话',
    value: '0',
    unit: '次',
    description: '流式交互会话统计',
    icon: DataAnalysis,
    color: '#f56c6c',
  },
];
</script>

<template>
  <div class="dashboard-page">
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
        <el-card class="stat-card" shadow="hover">
          <div class="stat-card-body flex-between">
            <div class="stat-info">
              <p class="stat-title">{{ card.title }}</p>
              <p class="stat-value">
                {{ card.value }}
                <span class="stat-unit">{{ card.unit }}</span>
              </p>
              <p class="stat-desc">{{ card.description }}</p>
            </div>
            <div class="stat-icon" :style="{ backgroundColor: card.color + '20', color: card.color }">
              <el-icon :size="28"><component :is="card.icon" /></el-icon>
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
}

.welcome-card {
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  border: none;
  color: #fff;

  :deep(.el-card__body) {
    padding: 28px 32px;
  }
}

.welcome-title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
}

.welcome-desc {
  margin: 0;
  font-size: 14px;
  opacity: 0.9;
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
  width: 56px;
  height: 56px;
  border-radius: 12px;
  flex-shrink: 0;
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
