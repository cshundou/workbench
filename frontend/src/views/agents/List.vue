<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Search } from '@element-plus/icons-vue';
import AgentCard from '@/components/agent/AgentCard.vue';
import AgentConfigForm from '@/components/agent/AgentConfigForm.vue';
import type { AgentFormData } from '@/components/agent/AgentConfigForm.vue';
import { createAgent, updateAgent, deleteAgent, copyAgent, enableAgentShare } from '@/api/agent';
import type { AgentInfo } from '@/api/agent';
import { useAgentStore } from '@/stores/agent';
import { useUserStore } from '@/stores/user';
import ApiKeyHintBanner from '@/components/settings/ApiKeyHintBanner.vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';

const router = useRouter();
const agentStore = useAgentStore();
const userStore = useUserStore();

const queryParams = reactive({
  page: 1,
  page_size: 12,
  keyword: '',
});

const dialogVisible = ref(false);
const editingAgent = ref<AgentInfo | null>(null);
const submitLoading = ref(false);

const canWrite = computed(() => userStore.hasPermission('agent:write'));
const canDelete = computed(() => userStore.hasPermission('agent:delete'));

/** 加载列表 */
async function fetchList(): Promise<void> {
  await agentStore.fetchAgents(queryParams);
  if (agentStore.availableTools.length === 0) {
    await agentStore.fetchAvailableTools();
  }
}

function handleSearch(): void {
  queryParams.page = 1;
  fetchList();
}

function handlePageChange(page: number): void {
  queryParams.page = page;
  fetchList();
}

function openCreateDialog(): void {
  editingAgent.value = null;
  dialogVisible.value = true;
}

function openEditDialog(agent: AgentInfo): void {
  editingAgent.value = agent;
  dialogVisible.value = true;
}

async function handleFormSubmit(form: AgentFormData): Promise<void> {
  submitLoading.value = true;
  try {
    if (editingAgent.value) {
      await updateAgent(editingAgent.value.id, form);
      ElMessage.success('更新成功');
    } else {
      await createAgent(form);
      ElMessage.success('创建成功');
    }
    dialogVisible.value = false;
    await fetchList();
  } catch (error) {
    console.error('[Agent Form Submit Error]', error);
  } finally {
    submitLoading.value = false;
  }
}

async function handleCopy(agent: AgentInfo): Promise<void> {
  try {
    await copyAgent(agent.id);
    ElMessage.success('复制成功');
    await fetchList();
  } catch (error) {
    console.error('[Copy Agent Error]', error);
  }
}

async function handleShare(agent: AgentInfo): Promise<void> {
  try {
    const result = await enableAgentShare(agent.id);
    const shareUrl = `${window.location.origin}/agents/share/${result.share_token}`;
    await ElMessageBox.alert(
      `分享链接：${shareUrl}`,
      '分享成功',
      { confirmButtonText: '复制链接' },
    );
    await navigator.clipboard.writeText(shareUrl);
    ElMessage.success('链接已复制到剪贴板');
  } catch (error) {
    console.error('[Share Agent Error]', error);
  }
}

async function handleDelete(agent: AgentInfo): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除智能体「${agent.name}」吗？`, '删除确认', {
      type: 'warning',
    });
    await deleteAgent(agent.id);
    ElMessage.success('删除成功');
    await fetchList();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Delete Agent Error]', error);
    }
  }
}

function goChat(agent: AgentInfo): void {
  router.push({ name: 'AgentChat', params: { id: agent.id } });
}

function goConfig(agent: AgentInfo): void {
  router.push({ name: 'AgentConfig', params: { id: agent.id } });
}

onMounted(() => {
  fetchList();
});
</script>

<template>
  <div class="agent-list-page">
    <ApiKeyHintBanner scene="agent" />

    <SectionHeader title="智能体中心" description="创建、配置和管理可调用工具的单 Agent 智能体">
      <template #actions>
        <el-button v-if="canWrite" type="primary" :icon="Plus" round @click="openCreateDialog">
          新建智能体
        </el-button>
      </template>
    </SectionHeader>

    <div class="search-bar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="搜索智能体名称"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
      >
        <template #append>
          <el-button :icon="Search" @click="handleSearch" />
        </template>
      </el-input>
    </div>

    <div v-loading="agentStore.isLoading" class="agent-grid">
      <el-empty
        v-if="!agentStore.isLoading && agentStore.agents.length === 0"
        description="暂无智能体"
      />

      <el-row v-else :gutter="16">
        <el-col
          v-for="agent in agentStore.agents"
          :key="agent.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
        >
          <AgentCard
            :agent="agent"
            :can-write="canWrite"
            :can-delete="canDelete"
            @edit="openEditDialog"
            @delete="handleDelete"
            @copy="handleCopy"
            @share="handleShare"
            @chat="goChat"
            @config="goConfig"
          />
        </el-col>
      </el-row>
    </div>

    <div v-if="agentStore.total > queryParams.page_size" class="pagination-wrap">
      <el-pagination
        background
        layout="prev, pager, next"
        :total="agentStore.total"
        :page-size="queryParams.page_size"
        :current-page="queryParams.page"
        @current-change="handlePageChange"
      />
    </div>

    <AgentConfigForm
      v-model="dialogVisible"
      :agent="editingAgent"
      :tools="agentStore.availableTools"
      :loading="submitLoading"
      @submit="handleFormSubmit"
    />
  </div>
</template>

<style lang="scss" scoped>
.agent-list-page {
  padding: 0;
}

.search-bar {
  margin-bottom: 24px;
}

.search-input {
  width: 280px;
}

.agent-grid {
  min-height: 300px;

  .el-col {
    margin-bottom: 16px;
  }
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
