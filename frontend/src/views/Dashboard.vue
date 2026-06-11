<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  Collection,
  Cpu,
  Share,
  DataAnalysis,
  Key,
  Document,
  Search,
  Connection,
} from '@element-plus/icons-vue';
import PageHero from '@/components/layout/PageHero.vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import FeatureBanner from '@/components/layout/FeatureBanner.vue';
import type { FeatureSlide } from '@/components/layout/FeatureBanner.vue';
import BentoCard from '@/components/layout/BentoCard.vue';
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

function goToKnowledge(): void {
  router.push('/knowledge');
}

onMounted(fetchApiKeyStatus);

/** Feature Banner 轮播数据 */
const featureSlides: FeatureSlide[] = [
  {
    title: '增强 RAG 系统',
    features: [
      { icon: Document, title: '智能分块', subtitle: '混合分块 + 语义分块' },
      { icon: Search, title: '双路检索', subtitle: '向量检索 + BM25' },
      { icon: Connection, title: '引用溯源', subtitle: '自动标注来源片段' },
    ],
  },
  {
    title: '单 Agent 智能体',
    features: [
      { icon: Cpu, title: '工具调用', subtitle: '知识库 / 搜索 / 代码执行' },
      { icon: Search, title: '任务规划', subtitle: '自主判断工具选择' },
      { icon: Document, title: '流式对话', subtitle: '思考过程实时可视化' },
    ],
  },
  {
    title: 'LangGraph 工作流',
    features: [
      { icon: Share, title: '多智能体编排', subtitle: '串行 / 并行 / 分支' },
      { icon: Connection, title: '人工介入', subtitle: '关键节点确认机制' },
      { icon: DataAnalysis, title: '状态追踪', subtitle: 'Redis 持久化不丢失' },
    ],
  },
];

/** 平台能力入口卡片 */
const moduleCards = [
  {
    title: '知识库',
    description: '企业私有知识沉淀与增强 RAG 问答',
    icon: Collection,
    path: '/knowledge',
  },
  {
    title: '智能体',
    description: '单 Agent 任务自动化与工具调用',
    icon: Cpu,
    path: '/agents',
  },
  {
    title: '工作流',
    description: 'LangGraph 多智能体协同编排',
    icon: Share,
    path: '/workflows',
  },
  {
    title: '监控面板',
    description: 'Token 消耗与接口调用统计',
    icon: DataAnalysis,
    path: '/monitor',
  },
];

/** 使用统计卡片 */
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
    <PageHero
      :title="welcomeText"
      subtitle="企业智能协作工作台 · 知识问答 · 任务自动化 · 多智能体协同"
      :actions="[
        { label: '配置 API 密钥', type: 'primary', onClick: goToApiKeys },
        { label: '快速开始', type: 'default', onClick: goToKnowledge },
      ]"
    />

    <!-- API Key 引导提示 -->
    <div v-if="needsApiKeySetup" class="api-key-tip">
      <el-icon class="tip-icon"><Key /></el-icon>
      <span class="tip-text"> 开始使用前，请先在「API 密钥管理」中配置您的大模型密钥 </span>
      <el-button type="primary" size="small" round @click="goToApiKeys">前往配置</el-button>
    </div>

    <FeatureBanner :slides="featureSlides" />

    <!-- 平台能力入口 -->
    <section class="section-block">
      <SectionHeader
        title="平台能力"
        description="MiniMax 最新首推能力，覆盖知识库 / 智能体 / 工作流 / 监控"
      />
      <el-row :gutter="20">
        <el-col v-for="card in moduleCards" :key="card.title" :xs="24" :sm="12" :lg="6">
          <BentoCard
            :title="card.title"
            :description="card.description"
            :icon="card.icon"
            clickable
            class="module-card"
            @click="router.push(card.path)"
          />
        </el-col>
      </el-row>
    </section>

    <!-- 使用统计 -->
    <section class="section-block">
      <SectionHeader title="使用统计" description="平台资源与交互数据概览" />
      <el-row :gutter="20">
        <el-col v-for="card in statCards" :key="card.title" :xs="24" :sm="12" :lg="6">
          <BentoCard
            :title="card.title"
            :value="card.value"
            :unit="card.unit"
            :description="card.description"
            :icon="card.icon"
          />
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<style lang="scss" scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
}

.api-key-tip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  margin-bottom: 32px;
  background: rgba($primary-color, 0.08);
  border-radius: $border-radius-pill;
}

.tip-icon {
  color: $primary-color;
  font-size: 18px;
  flex-shrink: 0;
}

.tip-text {
  flex: 1;
  font-size: 14px;
  color: $text-regular;
}

.module-card {
  margin-bottom: 20px;
}
</style>
