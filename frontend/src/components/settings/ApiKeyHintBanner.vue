<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { getApiKeyStatus, type UserApiKeyStatus } from '@/api/apiKeys';

const props = defineProps<{
  /** 使用场景：rag 知识库 / agent 智能体 / workflow 工作流 */
  scene: 'rag' | 'agent' | 'workflow';
}>();

const router = useRouter();
const loading = ref(false);
const status = ref<UserApiKeyStatus | null>(null);

/** 根据场景判断是否需要显示提示 */
const showHint = ref(false);
const hintMessage = ref('');

function buildHintMessage(): void {
  if (!status.value) {
    return;
  }

  if (props.scene === 'rag') {
    if (status.value.missing_for_rag.length > 0) {
      showHint.value = true;
      if (!status.value.has_llm_key && !status.value.has_embedding_key) {
        hintMessage.value =
          '使用知识库问答和文档解析需要配置大模型 API 密钥（用于 Embedding 与问答生成）。';
      } else if (!status.value.has_embedding_key) {
        hintMessage.value = '文档向量化需要配置支持 Embedding 的大模型 API 密钥。';
      } else {
        hintMessage.value = '知识库问答需要配置至少一个大模型 API 密钥。';
      }
    }
    return;
  }

  if (props.scene === 'agent' || props.scene === 'workflow') {
    if (!status.value.has_llm_key) {
      showHint.value = true;
      hintMessage.value =
        props.scene === 'agent'
          ? '智能体对话需要配置至少一个大模型 API 密钥。'
          : '工作流执行需要配置至少一个大模型 API 密钥。';
    }
  }
}

async function fetchStatus(): Promise<void> {
  loading.value = true;
  try {
    status.value = await getApiKeyStatus();
    buildHintMessage();
  } catch (error) {
    console.error('[Fetch API Key Status Error]', error);
  } finally {
    loading.value = false;
  }
}

function goToSettings(): void {
  router.push('/settings/api-keys');
}

onMounted(fetchStatus);

defineExpose({ refresh: fetchStatus });
</script>

<template>
  <el-alert
    v-if="showHint"
    v-loading="loading"
    type="warning"
    show-icon
    :closable="false"
    class="api-key-hint"
    title="尚未配置必要的 API 密钥"
  >
    <template #default>
      <p class="hint-text">{{ hintMessage }}</p>
      <el-button type="primary" link @click="goToSettings">前往 API 密钥管理</el-button>
    </template>
  </el-alert>
</template>

<style lang="scss" scoped>
.api-key-hint {
  margin-bottom: 16px;
}

.hint-text {
  margin: 0 0 4px;
  line-height: 1.5;
}
</style>
