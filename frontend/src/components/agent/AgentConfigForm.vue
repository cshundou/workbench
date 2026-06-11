<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { Rank } from '@element-plus/icons-vue';
import type { FormInstance, FormRules } from 'element-plus';
import type { AgentInfo, ToolDefinition } from '@/api/agent';
import PromptEditor from '@/components/agent/PromptEditor.vue';
import {
  LLM_MODEL_DEFINITIONS,
  LLM_PROVIDER_ORDER,
  PROVIDER_LABELS,
  getModelMaxTokens,
  validateAgentModelParams,
  type ModelDefinition,
} from '@/constants/models';

const props = withDefaults(
  defineProps<{
    modelValue?: boolean;
    agent?: AgentInfo | null;
    tools: ToolDefinition[];
    loading?: boolean;
    inline?: boolean;
  }>(),
  {
    modelValue: false,
    agent: null,
    loading: false,
    inline: false,
  },
);

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  submit: [form: AgentFormData];
}>();

export interface AgentFormData {
  name: string;
  description: string;
  system_prompt: string;
  model_name: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  model_priorities: string[];
  is_public: boolean;
  tools: string[];
}

const formRef = ref<FormInstance>();

const form = reactive<AgentFormData>({
  name: '',
  description: '',
  system_prompt: '你是一个专业的企业智能助手，能够使用工具帮助用户解决问题。',
  model_name: 'gpt-3.5-turbo',
  temperature: 0.7,
  top_p: 1,
  max_tokens: 2048,
  model_priorities: ['gpt-3.5-turbo'],
  is_public: false,
  tools: [],
});

const modelsByProvider = computed(() => {
  const grouped: Record<string, ModelDefinition[]> = {};
  for (const provider of LLM_PROVIDER_ORDER) {
    grouped[provider] = LLM_MODEL_DEFINITIONS.filter((m) => m.provider === provider);
  }
  return grouped;
});

const currentModelDef = computed(
  () => LLM_MODEL_DEFINITIONS.find((m) => m.name === form.model_name),
);

const maxTokensLimit = computed(() => getModelMaxTokens(form.model_name));

const paramHint = computed(() => {
  const def = currentModelDef.value;
  if (!def) return '';
  return `建议：温度 ${def.defaultTemperature}，Top P ${def.defaultTopP}，最大 Token ≤ ${def.maxTokens}`;
});

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入智能体名称', trigger: 'blur' },
    { min: 2, max: 100, message: '名称长度为 2-100 个字符', trigger: 'blur' },
  ],
  system_prompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }],
};

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
});

const isEdit = computed(() => !!props.agent?.id);

function syncModelPriorities(): void {
  if (!form.model_priorities.includes(form.model_name)) {
    form.model_priorities = [form.model_name, ...form.model_priorities];
  }
}

function fillForm(agent: AgentInfo): void {
  form.name = agent.name;
  form.description = agent.description || '';
  form.system_prompt = agent.system_prompt;
  form.model_name = agent.model_name;
  form.temperature = agent.temperature;
  form.top_p = agent.top_p ?? 1;
  form.max_tokens = agent.max_tokens;
  form.model_priorities = agent.model_priorities?.length
    ? [...agent.model_priorities]
    : [agent.model_name];
  form.is_public = agent.is_public;
  form.tools = [...agent.tools];
}

function resetForm(): void {
  form.name = '';
  form.description = '';
  form.system_prompt = '你是一个专业的企业智能助手，能够使用工具帮助用户解决问题。';
  form.model_name = 'gpt-3.5-turbo';
  form.temperature = 0.7;
  form.top_p = 1;
  form.max_tokens = 2048;
  form.model_priorities = ['gpt-3.5-turbo'];
  form.is_public = false;
  form.tools = [];
}

watch(
  () => props.agent,
  (agent) => {
    if (agent) {
      fillForm(agent);
    } else {
      resetForm();
    }
  },
  { immediate: true },
);

watch(
  () => form.model_name,
  (name) => {
    const limit = getModelMaxTokens(name);
    if (form.max_tokens > limit) {
      form.max_tokens = limit;
    }
    syncModelPriorities();
  },
);

function togglePriorityModel(modelName: string): void {
  const idx = form.model_priorities.indexOf(modelName);
  if (idx >= 0) {
    if (form.model_priorities.length <= 1) {
      ElMessage.warning('至少保留一个模型优先级');
      return;
    }
    form.model_priorities.splice(idx, 1);
  } else {
    form.model_priorities.push(modelName);
  }
}

function movePriority(index: number, direction: -1 | 1): void {
  const target = index + direction;
  if (target < 0 || target >= form.model_priorities.length) return;
  const items = [...form.model_priorities];
  [items[index], items[target]] = [items[target], items[index]];
  form.model_priorities = items;
}

function getModelLabel(name: string): string {
  return LLM_MODEL_DEFINITIONS.find((m) => m.name === name)?.label ?? name;
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  const error = validateAgentModelParams(
    form.model_name,
    form.temperature,
    form.top_p,
    form.max_tokens,
  );
  if (error) {
    ElMessage.error(error);
    return;
  }

  emit('submit', { ...form, model_priorities: [...form.model_priorities] });
}
</script>

<template>
  <!-- 弹窗模式（列表页新建/编辑） -->
  <el-dialog
    v-if="!inline"
    v-model="dialogVisible"
    :title="isEdit ? '编辑智能体' : '新建智能体'"
    width="760px"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入智能体名称" />
      </el-form-item>

      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="2"
          placeholder="简要描述智能体用途"
        />
      </el-form-item>

      <el-form-item label="系统提示词" prop="system_prompt">
        <PromptEditor v-model="form.system_prompt" height="220px" />
      </el-form-item>

      <el-form-item label="主模型">
        <el-select v-model="form.model_name" style="width: 100%">
          <el-option-group
            v-for="provider in LLM_PROVIDER_ORDER"
            :key="provider"
            :label="PROVIDER_LABELS[provider]"
          >
            <el-option
              v-for="item in modelsByProvider[provider]"
              :key="item.name"
              :label="item.label"
              :value="item.name"
            />
          </el-option-group>
        </el-select>
        <div v-if="paramHint" class="param-hint">{{ paramHint }}</div>
      </el-form-item>

      <el-form-item label="温度">
        <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input />
        <div class="param-hint">范围 0-2，步长 0.1，默认 0.7</div>
      </el-form-item>

      <el-form-item label="Top P">
        <el-slider v-model="form.top_p" :min="0" :max="1" :step="0.1" show-input />
        <div class="param-hint">范围 0-1，步长 0.1，默认 1.0</div>
      </el-form-item>

      <el-form-item label="最大 Token">
        <el-input-number
          v-model="form.max_tokens"
          :min="1"
          :max="maxTokensLimit"
          :step="256"
        />
        <div class="param-hint">范围 1-{{ maxTokensLimit }}（随所选模型自动限制）</div>
      </el-form-item>

      <el-form-item label="模型优先级">
        <div class="priority-panel">
          <p class="priority-desc">故障时按以下顺序自动降级，可拖动调整优先级</p>
          <div
            v-for="(modelName, index) in form.model_priorities"
            :key="modelName"
            class="priority-item"
          >
            <el-icon class="drag-handle"><Rank /></el-icon>
            <span class="priority-rank">{{ index + 1 }}</span>
            <span class="priority-label">{{ getModelLabel(modelName) }}</span>
            <el-button-group size="small">
              <el-button :disabled="index === 0" @click="movePriority(index, -1)">上移</el-button>
              <el-button
                :disabled="index === form.model_priorities.length - 1"
                @click="movePriority(index, 1)"
              >
                下移
              </el-button>
            </el-button-group>
          </div>
          <div class="priority-add">
            <span class="priority-add-label">添加降级模型：</span>
            <el-check-tag
              v-for="item in LLM_MODEL_DEFINITIONS"
              :key="item.name"
              :checked="form.model_priorities.includes(item.name)"
              class="priority-tag"
              @change="togglePriorityModel(item.name)"
            >
              {{ item.label }}
            </el-check-tag>
          </div>
        </div>
      </el-form-item>

      <el-form-item label="可用工具">
        <el-checkbox-group v-model="form.tools">
          <div v-for="tool in tools" :key="tool.name" class="tool-option">
            <el-checkbox :label="tool.name" :value="tool.name">
              {{ tool.label }}
            </el-checkbox>
            <span class="tool-desc">{{ tool.description }}</span>
          </div>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item label="公开">
        <el-switch v-model="form.is_public" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>

  <!-- 内联模式（配置页） -->
  <el-form
    v-else
    ref="formRef"
    :model="form"
    :rules="formRules"
    label-width="110px"
    class="inline-form"
  >
    <el-form-item label="名称" prop="name">
      <el-input v-model="form.name" placeholder="请输入智能体名称" />
    </el-form-item>

    <el-form-item label="描述">
      <el-input v-model="form.description" type="textarea" :rows="2" />
    </el-form-item>

    <el-form-item label="系统提示词" prop="system_prompt">
      <PromptEditor v-model="form.system_prompt" height="280px" />
    </el-form-item>

    <el-form-item label="主模型">
      <el-select v-model="form.model_name" style="width: 100%">
        <el-option-group
          v-for="provider in LLM_PROVIDER_ORDER"
          :key="provider"
          :label="PROVIDER_LABELS[provider]"
        >
          <el-option
            v-for="item in modelsByProvider[provider]"
            :key="item.name"
            :label="item.label"
            :value="item.name"
          />
        </el-option-group>
      </el-select>
      <div v-if="paramHint" class="param-hint">{{ paramHint }}</div>
    </el-form-item>

    <el-form-item label="温度">
      <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input />
    </el-form-item>

    <el-form-item label="Top P">
      <el-slider v-model="form.top_p" :min="0" :max="1" :step="0.1" show-input />
    </el-form-item>

    <el-form-item label="最大 Token">
      <el-input-number
        v-model="form.max_tokens"
        :min="1"
        :max="maxTokensLimit"
        :step="256"
      />
    </el-form-item>

    <el-form-item label="模型优先级">
      <div class="priority-panel">
        <div
          v-for="(modelName, index) in form.model_priorities"
          :key="modelName"
          class="priority-item"
        >
          <span class="priority-rank">{{ index + 1 }}</span>
          <span>{{ getModelLabel(modelName) }}</span>
          <el-button-group size="small">
            <el-button :disabled="index === 0" @click="movePriority(index, -1)">上移</el-button>
            <el-button
              :disabled="index === form.model_priorities.length - 1"
              @click="movePriority(index, 1)"
            >
              下移
            </el-button>
          </el-button-group>
        </div>
      </div>
    </el-form-item>

    <el-form-item label="可用工具">
      <el-checkbox-group v-model="form.tools">
        <div v-for="tool in tools" :key="tool.name" class="tool-option">
          <el-checkbox :label="tool.name" :value="tool.name">{{ tool.label }}</el-checkbox>
          <span class="tool-desc">{{ tool.description }}</span>
        </div>
      </el-checkbox-group>
    </el-form-item>

    <el-form-item label="公开">
      <el-switch v-model="form.is_public" />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" :loading="loading" @click="handleSubmit">保存配置</el-button>
    </el-form-item>
  </el-form>
</template>

<style lang="scss" scoped>
.tool-option {
  display: flex;
  flex-direction: column;
  margin-bottom: 8px;
}

.tool-desc {
  margin-left: 24px;
  font-size: 12px;
  color: $text-secondary;
}

.param-hint {
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
}

.priority-panel {
  width: 100%;
}

.priority-desc {
  margin: 0 0 8px;
  font-size: 12px;
  color: $text-secondary;
}

.priority-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.drag-handle {
  cursor: grab;
  color: $text-secondary;
}

.priority-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
}

.priority-label {
  flex: 1;
}

.priority-add {
  margin-top: 12px;
}

.priority-add-label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  color: $text-secondary;
}

.priority-tag {
  margin: 0 8px 8px 0;
}

.inline-form {
  max-width: 720px;
}
</style>
