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
} from '@/api/apiKeys';
import {
  fetchProviderModels,
  getModelLabel,
  listModelProviders,
  type AIModelEntity,
  type ModelProviderInfo,
} from '@/api/models';
import SectionHeader from '@/components/layout/SectionHeader.vue';

interface ProviderConfig extends ModelProviderInfo {
  name: string;
}

interface ProviderFormState {
  apiKey: string;
  baseUrl: string;
  modelName: string;
  embeddingModelName: string;
  isDefault: boolean;
  showKey: boolean;
  savedMasked: string;
  hasSaved: boolean;
  validating: boolean;
  saving: boolean;
  modelsLoading: boolean;
  validateStatus: 'idle' | 'success' | 'error';
  validateMessage: string;
  modelsWarning: string;
}

interface ProviderModelOptions {
  llm: AIModelEntity[];
  embedding: AIModelEntity[];
  rerank: AIModelEntity[];
}

const loading = ref(false);
const providerConfigs = ref<ProviderConfig[]>([]);

const formStates = reactive<Record<string, ProviderFormState>>({});
const modelOptions = reactive<Record<string, ProviderModelOptions>>({});

function createEmptyState(): ProviderFormState {
  return {
    apiKey: '',
    baseUrl: '',
    modelName: '',
    embeddingModelName: '',
    isDefault: false,
    showKey: false,
    savedMasked: '',
    hasSaved: false,
    validating: false,
    saving: false,
    modelsLoading: false,
    validateStatus: 'idle',
    validateMessage: '',
    modelsWarning: '',
  };
}

function createEmptyModelOptions(): ProviderModelOptions {
  return { llm: [], embedding: [], rerank: [] };
}

const llmProviders = computed(() =>
  providerConfigs.value.filter((item) => item.category === 'llm'),
);
const toolProviders = computed(() =>
  providerConfigs.value.filter(
    (item) => item.category === 'tool' && item.provider !== 'cohere',
  ),
);
const cohereConfig = computed(() =>
  providerConfigs.value.find((item) => item.provider === 'cohere'),
);

const LLM_PROVIDER_LABELS: Record<string, string> = {
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

async function loadProviderConfigs(): Promise<void> {
  const providers = await listModelProviders();
  providerConfigs.value = providers.map((item) => ({
    ...item,
    name: item.label.zh_Hans || item.label.en_US || item.provider,
  }));
  for (const config of providerConfigs.value) {
    if (!formStates[config.provider]) {
      formStates[config.provider] = createEmptyState();
    }
    if (!modelOptions[config.provider]) {
      modelOptions[config.provider] = createEmptyModelOptions();
    }
  }
}

async function loadPredefinedModels(config: ProviderConfig): Promise<void> {
  try {
    const response = await fetchProviderModels(config.provider, {
      model_type: config.category === 'llm' ? undefined : 'rerank',
    });
    modelOptions[config.provider] = {
      llm: response.models.filter((m) => m.model_type === 'llm'),
      embedding: response.models.filter((m) => m.model_type === 'text-embedding'),
      rerank: response.models.filter((m) => m.model_type === 'rerank'),
    };
  } catch (error) {
    console.error('[Load Predefined Models Error]', error);
  }
}

async function loadProviderModels(
  config: ProviderConfig,
  apiKey?: string,
  forceRefresh = false,
): Promise<void> {
  const state = formStates[config.provider];
  state.modelsLoading = true;
  state.modelsWarning = '';
  try {
    const response = await fetchProviderModels(config.provider, {
      api_key: apiKey || state.apiKey.trim() || undefined,
      base_url: state.baseUrl.trim() || undefined,
      force_refresh: forceRefresh,
    });
    modelOptions[config.provider] = {
      llm: response.models.filter((m) => m.model_type === 'llm'),
      embedding: response.models.filter((m) => m.model_type === 'text-embedding'),
      rerank: response.models.filter((m) => m.model_type === 'rerank'),
    };
    if (response.warning) {
      state.modelsWarning = response.warning;
    }
    if (!state.modelName && modelOptions[config.provider].llm.length) {
      state.modelName = modelOptions[config.provider].llm[0].model;
    }
    if (!state.embeddingModelName && modelOptions[config.provider].embedding.length) {
      state.embeddingModelName = modelOptions[config.provider].embedding[0].model;
    }
  } catch (error) {
    console.error('[Load Provider Models Error]', error);
    state.modelsWarning = '加载失败，显示默认模型';
  } finally {
    state.modelsLoading = false;
  }
}

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

async function fetchKeys(): Promise<void> {
  loading.value = true;
  try {
    const savedKeys = await listApiKeys();
    for (const config of providerConfigs.value) {
      const saved = savedKeys.find((item) => item.provider === config.provider);
      const state = formStates[config.provider];
      if (saved) {
        state.hasSaved = true;
        state.savedMasked = saved.api_key_masked;
        state.baseUrl = saved.base_url || '';
        state.modelName = saved.model_name || '';
        state.embeddingModelName = saved.embedding_model_name || '';
        state.isDefault = saved.is_default;
        state.validateStatus = saved.is_valid ? 'success' : 'idle';
        if (config.category === 'llm' && saved.is_valid) {
          await loadProviderModels(config);
          if (saved.model_name) state.modelName = saved.model_name;
          if (saved.embedding_model_name) state.embeddingModelName = saved.embedding_model_name;
        }
      } else {
        Object.assign(state, createEmptyState());
      }
    }
  } catch (error) {
    console.error('[Fetch API Keys Error]', error);
  } finally {
    loading.value = false;
  }
}

function keyPreview(provider: string): string {
  const state = formStates[provider];
  if (!state) return '未配置';
  if (state.apiKey) {
    const trimmed = state.apiKey.trim();
    return trimmed.length <= 4 ? `****${trimmed}` : `****${trimmed.slice(-4)}`;
  }
  if (state.hasSaved && state.savedMasked) return state.savedMasked;
  return '未配置';
}

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
    const result = await validateApiKey(
      config.provider as ApiKeyProvider,
      state.apiKey.trim() || undefined,
      state.baseUrl.trim() || undefined,
    );
    state.validateStatus = result.is_valid ? 'success' : 'error';
    state.validateMessage = result.message;
    if (result.warning) state.modelsWarning = result.warning;

    if (result.is_valid && config.category === 'llm') {
      await loadProviderModels(config, state.apiKey.trim() || undefined);
      if (result.llm_models?.length && !state.modelName) {
        state.modelName = result.llm_models[0];
      }
      if (result.embedding_models?.length && !state.embeddingModelName) {
        state.embeddingModelName = result.embedding_models[0];
      }
      ElMessage.success(result.message);
    } else if (result.is_valid) {
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

async function handleSave(config: ProviderConfig): Promise<void> {
  const state = formStates[config.provider];
  if (!state.apiKey.trim()) {
    ElMessage.warning('请输入 API 密钥');
    return;
  }

  state.saving = true;
  try {
    const saved = await upsertApiKey({
      provider: config.provider as ApiKeyProvider,
      api_key: state.apiKey.trim(),
      base_url: state.baseUrl.trim() || undefined,
      model_name: state.modelName || undefined,
      embedding_model_name: state.embeddingModelName || undefined,
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
      await loadProviderModels(config);
    }
    await fetchKeys();
  } catch (error) {
    console.error('[Save API Key Error]', error);
  } finally {
    state.saving = false;
  }
  await fetchRerankPreference();
}

async function handleDelete(config: ProviderConfig): Promise<void> {
  const state = formStates[config.provider];
  if (!state.hasSaved) return;
  try {
    await deleteApiKey(config.provider as ApiKeyProvider);
    Object.assign(state, createEmptyState());
    modelOptions[config.provider] = createEmptyModelOptions();
    ElMessage.success(`${config.name} 密钥已删除`);
    await fetchKeys();
  } catch (error) {
    console.error('[Delete API Key Error]', error);
  }
  await fetchRerankPreference();
}

/** 手动刷新模型列表 */
async function handleRefreshModels(config: ProviderConfig): Promise<void> {
  const state = formStates[config.provider];
  if (!state.apiKey && !state.hasSaved) {
    ElMessage.warning('请先输入或保存 API 密钥');
    return;
  }
  await loadProviderModels(config, state.apiKey.trim() || undefined, true);
  ElMessage.success('模型列表已刷新');
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadProviderConfigs();
    for (const config of providerConfigs.value) {
      if (config.category === 'llm' || config.provider === 'cohere') {
        await loadPredefinedModels(config);
      }
    }
    await fetchKeys();
    await fetchRerankPreference();
  } finally {
    loading.value = false;
  }
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
                  :placeholder="config.base_url_placeholder"
                />
              </el-form-item>

              <el-form-item label="默认 LLM 模型">
                <div class="model-select-row">
                  <el-select
                    v-model="formStates[config.provider].modelName"
                    :loading="formStates[config.provider].modelsLoading"
                    :placeholder="
                      formStates[config.provider].modelsLoading
                        ? '正在加载可用模型…'
                        : '选择默认对话模型'
                    "
                    style="width: 100%"
                  >
                    <el-option
                      v-for="model in modelOptions[config.provider]?.llm || []"
                      :key="model.model"
                      :label="getModelLabel(model)"
                      :value="model.model"
                    />
                  </el-select>
                  <el-button
                    :loading="formStates[config.provider].modelsLoading"
                    @click="handleRefreshModels(config)"
                  >
                    刷新
                  </el-button>
                </div>
                <p v-if="formStates[config.provider].modelsWarning" class="models-warning">
                  {{ formStates[config.provider].modelsWarning }}
                </p>
              </el-form-item>

              <el-form-item label="默认 Embedding 模型">
                <div class="model-select-row">
                  <el-select
                    v-model="formStates[config.provider].embeddingModelName"
                    :loading="formStates[config.provider].modelsLoading"
                    :placeholder="
                      formStates[config.provider].modelsLoading
                        ? '正在加载可用模型…'
                        : '选择默认向量模型'
                    "
                    style="width: 100%"
                  >
                    <el-option
                      v-for="model in modelOptions[config.provider]?.embedding || []"
                      :key="model.model"
                      :label="getModelLabel(model)"
                      :value="model.model"
                    />
                  </el-select>
                  <el-button
                    :loading="formStates[config.provider].modelsLoading"
                    @click="handleRefreshModels(config)"
                  >
                    刷新
                  </el-button>
                </div>
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

          <el-form-item v-if="(modelOptions.cohere?.rerank || []).length" label="默认模型">
            <el-select
              v-model="formStates.cohere.modelName"
              placeholder="选择默认模型"
              style="width: 100%"
            >
              <el-option
                v-for="model in modelOptions.cohere?.rerank || []"
                :key="model.model"
                :label="getModelLabel(model)"
                :value="model.model"
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

              <el-form-item v-if="(modelOptions[config.provider]?.rerank || []).length" label="默认模型">
                <el-select
                  v-model="formStates[config.provider].modelName"
                  placeholder="选择默认模型"
                  style="width: 100%"
                >
                  <el-option
                    v-for="model in modelOptions[config.provider]?.rerank || []"
                    :key="model.model"
                    :label="getModelLabel(model)"
                    :value="model.model"
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

.models-warning {
  margin: 6px 0 0;
  font-size: 12px;
  color: $warning-color;
}

.model-select-row {
  display: flex;
  gap: 8px;
  width: 100%;
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
