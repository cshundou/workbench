<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Warning } from '@element-plus/icons-vue';
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
  <div v-if="showHint" class="api-key-hint">
    <el-icon class="hint-icon"><Warning /></el-icon>
    <span class="hint-text">{{ hintMessage }}</span>
    <el-button type="primary" size="small" round @click="goToSettings">前往配置</el-button>
  </div>
</template>

<style lang="scss" scoped>
.api-key-hint {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  margin-bottom: 20px;
  background: rgba($warning-color, 0.08);
  border-radius: $border-radius-pill;
}

.hint-icon {
  color: $warning-color;
  font-size: 18px;
  flex-shrink: 0;
}

.hint-text {
  flex: 1;
  font-size: 14px;
  color: $text-regular;
  line-height: 1.5;
}
</style>
