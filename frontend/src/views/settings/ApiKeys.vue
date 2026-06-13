<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { CircleCheck, CircleClose, View, Hide } from '@element-plus/icons-vue';
import {
  deleteApiKey,
  getRerankPreference,
  listApiKeys,
  saveRerankPreference,
  upsertApiKey,
  validateApiKey,
  type ApiKeyProvider,
  type RerankLlmProvider,
  type RerankMode,
  type UserApiKeyInfo,
} from '@/api/apiKeys';
import SectionHeader from '@/components/layout/SectionHeader.vue';

interface ProviderConfig {
  provider: ApiKeyProvider;
  name: string;
  category: 'llm' | 'tool';
  description: string;
  models: string[];
  defaultBaseUrl: string;
  baseUrlPlaceholder: string;
}

/** 支持的 API 密钥配置项 */
const PROVIDER_CONFIGS: ProviderConfig[] = [
  {
    provider: 'openai',
    name: 'OpenAI',
    category: 'llm',
    description: 'GPT 系列大模型与 Embedding',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo', 'text-embedding-3-small'],
    defaultBaseUrl: 'https://api.openai.com/v1',
    baseUrlPlaceholder: 'https://api.openai.com/v1',
  },
  {
    provider: 'tongyi',
    name: '通义千问',
    category: 'llm',
    description: '阿里云 DashScope 兼容 OpenAI 协议',
    models: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'text-embedding-v3'],
    defaultBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    baseUrlPlaceholder: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  },
  {
    provider: 'doubao',
    name: '豆包',
    category: 'llm',
    description: '火山引擎 Ark 大模型',
    models: ['doubao-pro-32k', 'doubao-lite-32k', 'doubao-embedding'],
    defaultBaseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    baseUrlPlaceholder: 'https://ark.cn-beijing.volces.com/api/v3',
  },
  {
    provider: 'minimax',
    name: 'MiniMax',
    category: 'llm',
    description: 'MiniMax 对话与 embo-01 向量模型',
    models: ['abab6.5-chat', 'abab6.5s-chat', 'embo-01'],
    defaultBaseUrl: '',
    baseUrlPlaceholder: '可选：Group ID（部分账号 Embedding 需要）',
  },
  {
    provider: 'tavily',
    name: 'Tavily 搜索',
    category: 'tool',
    description: '联网搜索工具，供智能体与工作流使用',
    models: [],
    defaultBaseUrl: '',
    baseUrlPlaceholder: '无需自定义地址',
  },
  {
    provider: 'cohere',
    name: 'Cohere 重排序',
    category: 'tool',
    description: '可选，仅在重排序选择「Cohere 专用」时需要',
    models: ['rerank-multilingual-v3.0', 'rerank-english-v3.0'],
    defaultBaseUrl: '',
    baseUrlPlaceholder: '无需自定义地址',
  },
  {
    provider: 'pinecone',
    name: 'Pinecone 向量库',
    category: 'tool',
    description: '可选的云端向量数据库',
    models: [],
    defaultBaseUrl: '',
    baseUrlPlaceholder: '无需自定义地址',
  },
];

interface ProviderFormState {
  apiKey: string;
  baseUrl: string;
  modelName: string;
  isDefault: boolean;
  showKey: boolean;
  savedMasked: string;
  hasSaved: boolean;
  validating: boolean;
  saving: boolean;
  validateStatus: 'idle' | 'success' | 'error';
  validateMessage: string;
}

const loading = ref(false);
const savedKeys = ref<UserApiKeyInfo[]>([]);

/** 各提供商表单状态 */
const formStates = reactive<Record<ApiKeyProvider, ProviderFormState>>(
  {} as Record<ApiKeyProvider, ProviderFormState>,
);

function createEmptyState(): ProviderFormState {
  return {
    apiKey: '',
    baseUrl: '',
    modelName: '',
    isDefault: false,
    showKey: false,
    savedMasked: '',
    hasSaved: false,
    validating: false,
    saving: false,
    validateStatus: 'idle',
    validateMessage: '',
  };
}

/** 初始化表单状态 */
function initFormStates(): void {
  for (const config of PROVIDER_CONFIGS) {
    if (!formStates[config.provider]) {
      formStates[config.provider] = {
        ...createEmptyState(),
        modelName: config.models[0] || '',
      };
    }
  }
}

// 同步初始化，避免首屏渲染时 formStates[provider] 为 undefined
initFormStates();

const llmProviders = computed(() => PROVIDER_CONFIGS.filter((item) => item.category === 'llm'));
const toolProviders = computed(() =>
  PROVIDER_CONFIGS.filter((item) => item.category === 'tool' && item.provider !== 'cohere'),
);
const cohereConfig = computed(() => PROVIDER_CONFIGS.find((item) => item.provider === 'cohere'));

/** 大模型提供商显示名 */
const LLM_PROVIDER_LABELS: Record<ApiKeyProvider, string> = {
  openai: 'OpenAI',
  tongyi: '通义千问',
  doubao: '豆包',
  minimax: 'MiniMax',
  tavily: 'Tavily 搜索',
  cohere: 'Cohere',
  pinecone: 'Pinecone',
};

const rerankMode = ref<RerankMode>('auto');
const availableRerankProviders = ref<RerankLlmProvider[]>([]);
const hasCohereKey = ref(false);
const rerankSaving = ref(false);

/** 重排序模式选项 */
const rerankModeOptions = computed(() => {
  const options: Array<{ value: RerankMode; label: string; disabled?: boolean }> = [
    { value: 'auto', label: '自动（优先 Cohere，否则使用已配置大模型 Embedding）' },
  ];

  for (const provider of availableRerankProviders.value) {
    options.push({
      value: provider,
      label: `使用 ${LLM_PROVIDER_LABELS[provider]}（复用已配置密钥）`,
    });
  }

  options.push({
    value: 'cohere',
    label: 'Cohere 专用',
    disabled: !hasCohereKey.value,
  });
  options.push({ value: 'off', label: '关闭重排序' });
  return options;
});

async function fetchRerankPreference(): Promise<void> {
  try {
    const preference = await getRerankPreference();
    rerankMode.value = preference.mode as RerankMode;
    availableRerankProviders.value = preference.available_llm_providers as RerankLlmProvider[];
    hasCohereKey.value = preference.has_cohere_key;
  } catch (error) {
    console.error('[Fetch Rerank Preference Error]', error);
  }
}

async function handleSaveRerankPreference(): Promise<void> {
  if (rerankMode.value === 'cohere' && !hasCohereKey.value) {
    ElMessage.warning('请先配置 Cohere API 密钥');
    return;
  }
  if (
    ['openai', 'tongyi', 'doubao', 'minimax'].includes(rerankMode.value) &&
    !availableRerankProviders.value.includes(rerankMode.value as RerankLlmProvider)
  ) {
    ElMessage.warning('请先在「大模型」中配置对应 API 密钥');
    return;
  }

  rerankSaving.value = true;
  try {
    const preference = await saveRerankPreference(rerankMode.value);
    availableRerankProviders.value = preference.available_llm_providers as RerankLlmProvider[];
    hasCohereKey.value = preference.has_cohere_key;
    ElMessage.success('重排序设置已保存');
  } catch (error) {
    console.error('[Save Rerank Preference Error]', error);
  } finally {
    rerankSaving.value = false;
  }
}

/** 加载已保存的密钥 */
async function fetchKeys(): Promise<void> {
  loading.value = true;
  try {
    savedKeys.value = await listApiKeys();
    for (const config of PROVIDER_CONFIGS) {
      const saved = savedKeys.value.find((item) => item.provider === config.provider);
      const state = formStates[config.provider];
      if (saved) {
        state.hasSaved = true;
        state.savedMasked = saved.api_key_masked;
        state.baseUrl = saved.base_url || '';
        state.modelName = saved.model_name || config.models[0] || '';
        state.isDefault = saved.is_default;
        state.validateStatus = saved.is_valid ? 'success' : 'idle';
      } else {
        state.hasSaved = false;
        state.savedMasked = '';
        state.baseUrl = '';
        state.modelName = config.models[0] || '';
        state.isDefault = false;
        state.validateStatus = 'idle';
      }
    }
  } catch (error) {
    console.error('[Fetch API Keys Error]', error);
  } finally {
    loading.value = false;
  }
}

/** 显示密钥末尾 4 位预览 */
function keyPreview(provider: ApiKeyProvider): string {
  const state = formStates[provider];
  if (state.apiKey) {
    const trimmed = state.apiKey.trim();
    if (trimmed.length <= 4) {
      return `****${trimmed}`;
    }
    return `****${trimmed.slice(-4)}`;
  }
  if (state.hasSaved && state.savedMasked) {
    return state.savedMasked;
  }
  return '未配置';
}

/** 测试连接 */
async function handleValidate(config: ProviderConfig): Promise<void> {
  const state = formStates[config.provider];
  if (!state.apiKey && !state.hasSaved) {
    ElMessage.warning('请先输入 API 密钥');
    return;
  }

  state.validating = true;
  state.validateStatus = 'idle';
  state.validateMessage = '';
  try {
    const result = await validateApiKey(config.provider, state.apiKey.trim() || undefined);
    state.validateStatus = result.is_valid ? 'success' : 'error';
    state.validateMessage = result.message;
    if (result.is_valid) {
      ElMessage.success(result.message);
    } else {
      ElMessage.error(result.message);
    }
  } catch (error) {
    state.validateStatus = 'error';
    state.validateMessage = error instanceof Error ? error.message : '验证失败';
  } finally {
    state.validating = false;
  }
}

/** 保存密钥 */
async function handleSave(config: ProviderConfig): Promise<void> {
  const state = formStates[config.provider];
  if (!state.apiKey.trim()) {
    ElMessage.warning('请输入 API 密钥');
    return;
  }

  state.saving = true;
  try {
    const saved = await upsertApiKey({
      provider: config.provider,
      api_key: state.apiKey.trim(),
      base_url: state.baseUrl.trim() || undefined,
      model_name: state.modelName || undefined,
      is_default: state.isDefault,
    });
    state.hasSaved = true;
    state.savedMasked = saved.api_key_masked;
    state.apiKey = '';
    state.showKey = false;
    state.validateStatus = saved.is_valid ? 'success' : 'error';
    state.validateMessage = saved.is_valid
      ? '密钥已保存并验证通过'
      : '密钥已保存，但验证未通过，请检查密钥是否正确';
    if (!saved.is_valid) {
      ElMessage.warning(state.validateMessage);
    } else {
      ElMessage.success(`${config.name} 密钥保存成功`);
    }
    await fetchKeys();
  } catch (error) {
    console.error('[Save API Key Error]', error);
  } finally {
    state.saving = false;
  }
  await fetchRerankPreference();
}

/** 删除密钥 */
async function handleDelete(config: ProviderConfig): Promise<void> {
  const state = formStates[config.provider];
  if (!state.hasSaved) {
    return;
  }
  try {
    await deleteApiKey(config.provider);
    Object.assign(state, createEmptyState());
    state.modelName = config.models[0] || '';
    ElMessage.success(`${config.name} 密钥已删除`);
    await fetchKeys();
  } catch (error) {
    console.error('[Delete API Key Error]', error);
  }
  await fetchRerankPreference();
}

onMounted(async () => {
  await fetchKeys();
  await fetchRerankPreference();
});
</script>

<template>
  <div v-loading="loading" class="api-keys-page">
    <SectionHeader
      title="API 密钥管理"
      description="配置您的 API 密钥以使用所有功能，所有密钥都将被加密存储"
    />

    <el-card shadow="never" class="intro-card">
      <p class="intro-text">
        至少配置一个大模型密钥，系统将按优先级自动降级（OpenAI → 通义 → 豆包 → MiniMax）
      </p>
    </el-card>

    <section class="provider-section">
      <h3 class="section-title">大模型</h3>
      <p class="section-desc">支持 OpenAI、通义千问、豆包、MiniMax 等主流大模型</p>
      <el-row :gutter="20">
        <el-col v-for="config in llmProviders" :key="config.provider" :xs="24" :lg="12">
          <el-card shadow="never" class="provider-card">
            <div class="provider-header">
              <div>
                <h4 class="provider-name">{{ config.name }}</h4>
                <p class="provider-desc">{{ config.description }}</p>
              </div>
              <el-tag v-if="formStates[config.provider].hasSaved" type="success" size="small">
                已配置
              </el-tag>
            </div>

            <el-form label-position="top" class="provider-form">
              <el-form-item label="API 密钥">
                <div class="key-input-row">
                  <el-input
                    v-model="formStates[config.provider].apiKey"
                    :type="formStates[config.provider].showKey ? 'text' : 'password'"
                    placeholder="输入 API 密钥"
                    autocomplete="off"
                  />
                  <el-button
                    text
                    :icon="formStates[config.provider].showKey ? Hide : View"
                    @click="
                      formStates[config.provider].showKey = !formStates[config.provider].showKey
                    "
                  />
                </div>
                <p class="key-preview">当前：{{ keyPreview(config.provider) }}</p>
              </el-form-item>

              <el-form-item label="自定义 API 地址（可选）">
                <el-input
                  v-model="formStates[config.provider].baseUrl"
                  :placeholder="config.baseUrlPlaceholder"
                />
              </el-form-item>

              <el-form-item v-if="config.models.length" label="默认模型">
                <el-select
                  v-model="formStates[config.provider].modelName"
                  placeholder="选择默认模型"
                  style="width: 100%"
                >
                  <el-option
                    v-for="model in config.models"
                    :key="model"
                    :label="model"
                    :value="model"
                  />
                </el-select>
              </el-form-item>

              <el-form-item>
                <el-checkbox v-model="formStates[config.provider].isDefault">
                  设为默认大模型（优先使用）
                </el-checkbox>
              </el-form-item>

              <div
                v-if="formStates[config.provider].validateStatus !== 'idle'"
                class="validate-result"
              >
                <el-icon
                  :class="
                    formStates[config.provider].validateStatus === 'success'
                      ? 'success-icon'
                      : 'error-icon'
                  "
                >
                  <CircleCheck v-if="formStates[config.provider].validateStatus === 'success'" />
                  <CircleClose v-else />
                </el-icon>
                <span>{{ formStates[config.provider].validateMessage }}</span>
              </div>

              <div class="action-row">
                <el-button
                  :loading="formStates[config.provider].validating"
                  @click="handleValidate(config)"
                >
                  测试连接
                </el-button>
                <el-button
                  type="primary"
                  :loading="formStates[config.provider].saving"
                  @click="handleSave(config)"
                >
                  保存
                </el-button>
                <el-button
                  v-if="formStates[config.provider].hasSaved"
                  type="danger"
                  plain
                  @click="handleDelete(config)"
                >
                  删除
                </el-button>
              </div>
            </el-form>
          </el-card>
        </el-col>
      </el-row>
    </section>

    <section class="provider-section">
      <h3 class="section-title">RAG 重排序</h3>
      <p class="section-desc">
        知识库检索后可二次排序提升相关性。可直接复用上方已配置的大模型 Embedding，无需单独购买 Cohere。
      </p>
      <el-card shadow="never" class="provider-card rerank-card">
        <el-form label-position="top" class="provider-form">
          <el-form-item label="重排序策略">
            <el-select v-model="rerankMode" placeholder="选择重排序策略" style="width: 100%">
              <el-option
                v-for="option in rerankModeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
                :disabled="option.disabled"
              />
            </el-select>
          </el-form-item>
          <p v-if="availableRerankProviders.length === 0" class="rerank-hint">
            尚未配置大模型密钥，请先在上方「大模型」区域配置 OpenAI / 通义 / 豆包 / MiniMax 等。
          </p>
          <p v-else class="rerank-hint">
            已检测到 {{ availableRerankProviders.map((p) => LLM_PROVIDER_LABELS[p]).join('、') }} 密钥，可直接选择使用。
          </p>
          <div class="action-row">
            <el-button type="primary" :loading="rerankSaving" @click="handleSaveRerankPreference">
              保存重排序设置
            </el-button>
          </div>
        </el-form>
      </el-card>

      <el-card
        v-if="cohereConfig && rerankMode === 'cohere'"
        shadow="never"
        class="provider-card"
      >
        <div class="provider-header">
          <div>
            <h4 class="provider-name">{{ cohereConfig.name }}</h4>
            <p class="provider-desc">{{ cohereConfig.description }}</p>
          </div>
          <el-tag v-if="formStates.cohere.hasSaved" type="success" size="small">已配置</el-tag>
        </div>

        <el-form label-position="top" class="provider-form">
          <el-form-item label="API 密钥">
            <div class="key-input-row">
              <el-input
                v-model="formStates.cohere.apiKey"
                :type="formStates.cohere.showKey ? 'text' : 'password'"
                placeholder="输入 Cohere API 密钥"
                autocomplete="off"
              />
              <el-button
                text
                :icon="formStates.cohere.showKey ? Hide : View"
                @click="formStates.cohere.showKey = !formStates.cohere.showKey"
              />
            </div>
            <p class="key-preview">当前：{{ keyPreview('cohere') }}</p>
          </el-form-item>

          <el-form-item v-if="cohereConfig.models.length" label="默认模型">
            <el-select v-model="formStates.cohere.modelName" placeholder="选择默认模型" style="width: 100%">
              <el-option
                v-for="model in cohereConfig.models"
                :key="model"
                :label="model"
                :value="model"
              />
            </el-select>
          </el-form-item>

          <div class="action-row">
            <el-button :loading="formStates.cohere.validating" @click="handleValidate(cohereConfig)">
              测试连接
            </el-button>
            <el-button type="primary" :loading="formStates.cohere.saving" @click="handleSave(cohereConfig)">
              保存
            </el-button>
            <el-button
              v-if="formStates.cohere.hasSaved"
              type="danger"
              plain
              @click="handleDelete(cohereConfig)"
            >
              删除
            </el-button>
          </div>
        </el-form>
      </el-card>
    </section>

    <section class="provider-section">
      <h3 class="section-title">工具</h3>
      <p class="section-desc">按需配置搜索与向量库相关密钥</p>
      <el-row :gutter="20">
        <el-col v-for="config in toolProviders" :key="config.provider" :xs="24" :lg="12">
          <el-card shadow="never" class="provider-card">
            <div class="provider-header">
              <div>
                <h4 class="provider-name">{{ config.name }}</h4>
                <p class="provider-desc">{{ config.description }}</p>
              </div>
              <el-tag v-if="formStates[config.provider].hasSaved" type="success" size="small">
                已配置
              </el-tag>
            </div>

            <el-form label-position="top" class="provider-form">
              <el-form-item label="API 密钥">
                <div class="key-input-row">
                  <el-input
                    v-model="formStates[config.provider].apiKey"
                    :type="formStates[config.provider].showKey ? 'text' : 'password'"
                    placeholder="输入 API 密钥"
                    autocomplete="off"
                  />
                  <el-button
                    text
                    :icon="formStates[config.provider].showKey ? Hide : View"
                    @click="
                      formStates[config.provider].showKey = !formStates[config.provider].showKey
                    "
                  />
                </div>
                <p class="key-preview">当前：{{ keyPreview(config.provider) }}</p>
              </el-form-item>

              <el-form-item v-if="config.models.length" label="默认模型">
                <el-select
                  v-model="formStates[config.provider].modelName"
                  placeholder="选择默认模型"
                  style="width: 100%"
                >
                  <el-option
                    v-for="model in config.models"
                    :key="model"
                    :label="model"
                    :value="model"
                  />
                </el-select>
              </el-form-item>

              <div
                v-if="formStates[config.provider].validateStatus !== 'idle'"
                class="validate-result"
              >
                <el-icon
                  :class="
                    formStates[config.provider].validateStatus === 'success'
                      ? 'success-icon'
                      : 'error-icon'
                  "
                >
                  <CircleCheck v-if="formStates[config.provider].validateStatus === 'success'" />
                  <CircleClose v-else />
                </el-icon>
                <span>{{ formStates[config.provider].validateMessage }}</span>
              </div>

              <div class="action-row">
                <el-button
                  :loading="formStates[config.provider].validating"
                  @click="handleValidate(config)"
                >
                  测试连接
                </el-button>
                <el-button
                  type="primary"
                  :loading="formStates[config.provider].saving"
                  @click="handleSave(config)"
                >
                  保存
                </el-button>
                <el-button
                  v-if="formStates[config.provider].hasSaved"
                  type="danger"
                  plain
                  @click="handleDelete(config)"
                >
                  删除
                </el-button>
              </div>
            </el-form>
          </el-card>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<style lang="scss" scoped>
.api-keys-page {
  max-width: 1200px;
}

.intro-card {
  margin-bottom: 24px;
}

.intro-text {
  margin: 0;
  color: $text-regular;
  line-height: 1.6;
}

.provider-section {
  margin-bottom: 32px;
}

.section-title {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 600;
  color: $text-primary;
}

.section-desc {
  margin: 0 0 16px;
  color: $text-secondary;
  font-size: 14px;
}

.rerank-card {
  max-width: 720px;
}

.rerank-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: $text-secondary;
  line-height: 1.6;
}

.provider-card {
  margin-bottom: 20px;
}

.provider-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.provider-name {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.provider-desc {
  margin: 0;
  font-size: 13px;
  color: $text-secondary;
}

.key-input-row {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
}

.key-preview {
  margin: 6px 0 0;
  font-size: 12px;
  color: $text-secondary;
}

.validate-result {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  font-size: 13px;
}

.success-icon {
  color: $success-color;
}

.error-icon {
  color: $danger-color;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
