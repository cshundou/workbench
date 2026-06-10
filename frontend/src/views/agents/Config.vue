<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft } from '@element-plus/icons-vue';
import AgentConfigForm from '@/components/agent/AgentConfigForm.vue';
import type { AgentFormData } from '@/components/agent/AgentConfigForm.vue';
import { updateAgent } from '@/api/agent';
import { useAgentStore } from '@/stores/agent';
import { useUserStore } from '@/stores/user';

const route = useRoute();
const router = useRouter();
const agentStore = useAgentStore();
const userStore = useUserStore();

const agentId = computed(() => Number(route.params.id));
const submitLoading = ref(false);

const canWrite = computed(() => userStore.hasPermission('agent:write'));

async function loadData(): Promise<void> {
  await Promise.all([
    agentStore.fetchAgent(agentId.value),
    agentStore.fetchAvailableTools(),
  ]);
}

async function handleSubmit(form: AgentFormData): Promise<void> {
  if (!canWrite.value) {
    ElMessage.warning('无编辑权限');
    return;
  }

  submitLoading.value = true;
  try {
    await updateAgent(agentId.value, form);
    ElMessage.success('配置已保存');
    await agentStore.fetchAgent(agentId.value);
  } catch (error) {
    console.error('[Update Agent Config Error]', error);
  } finally {
    submitLoading.value = false;
  }
}

function goBack(): void {
  router.push({ name: 'AgentList' });
}

function goChat(): void {
  router.push({ name: 'AgentChat', params: { id: agentId.value } });
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="agent-config-page">
    <div class="page-header flex-between">
      <div class="header-left flex-center">
        <el-button text :icon="ArrowLeft" @click="goBack">返回列表</el-button>
        <h2 class="page-title">{{ agentStore.currentAgent?.name || '智能体配置' }}</h2>
      </div>
      <el-button type="primary" @click="goChat">进入对话</el-button>
    </div>

    <el-card v-loading="agentStore.isLoading" shadow="never">
      <AgentConfigForm
        v-if="agentStore.currentAgent && canWrite"
        inline
        :agent="agentStore.currentAgent"
        :tools="agentStore.availableTools"
        :loading="submitLoading"
        @submit="handleSubmit"
      />
      <el-descriptions
        v-else-if="agentStore.currentAgent"
        :column="1"
        border
        class="readonly-config"
      >
        <el-descriptions-item label="名称">{{ agentStore.currentAgent.name }}</el-descriptions-item>
        <el-descriptions-item label="描述">
          {{ agentStore.currentAgent.description || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="模型">{{ agentStore.currentAgent.model_name }}</el-descriptions-item>
        <el-descriptions-item label="温度">{{ agentStore.currentAgent.temperature }}</el-descriptions-item>
        <el-descriptions-item label="最大 Token">{{ agentStore.currentAgent.max_tokens }}</el-descriptions-item>
        <el-descriptions-item label="工具">
          <el-tag
            v-for="tool in agentStore.currentAgent.tools"
            :key="tool"
            size="small"
            style="margin-right: 6px"
          >
            {{ tool }}
          </el-tag>
          <span v-if="!agentStore.currentAgent.tools.length">未启用工具</span>
        </el-descriptions-item>
        <el-descriptions-item label="系统提示词">
          <pre class="prompt-preview">{{ agentStore.currentAgent.system_prompt }}</pre>
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-else-if="!agentStore.isLoading && !agentStore.currentAgent" description="智能体不存在" />
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.agent-config-page {
  max-width: 900px;
}

.page-header {
  margin-bottom: 16px;
}

.header-left {
  gap: 8px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.prompt-preview {
  margin: 0;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  max-height: 240px;
  overflow-y: auto;
}

.readonly-config {
  max-width: 720px;
}
</style>
