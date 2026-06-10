<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import type { AgentInfo, ToolDefinition } from '@/api/agent';

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
  max_tokens: number;
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
  max_tokens: 2048,
  is_public: false,
  tools: [],
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

function fillForm(agent: AgentInfo): void {
  form.name = agent.name;
  form.description = agent.description || '';
  form.system_prompt = agent.system_prompt;
  form.model_name = agent.model_name;
  form.temperature = agent.temperature;
  form.max_tokens = agent.max_tokens;
  form.is_public = agent.is_public;
  form.tools = [...agent.tools];
}

function resetForm(): void {
  form.name = '';
  form.description = '';
  form.system_prompt = '你是一个专业的企业智能助手，能够使用工具帮助用户解决问题。';
  form.model_name = 'gpt-3.5-turbo';
  form.temperature = 0.7;
  form.max_tokens = 2048;
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

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  emit('submit', { ...form });
}
</script>

<template>
  <!-- 弹窗模式（列表页新建/编辑） -->
  <el-dialog
    v-if="!inline"
    v-model="dialogVisible"
    :title="isEdit ? '编辑智能体' : '新建智能体'"
    width="720px"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
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
        <el-input
          v-model="form.system_prompt"
          type="textarea"
          :rows="6"
          placeholder="定义智能体角色与行为准则"
        />
      </el-form-item>

      <el-form-item label="模型">
        <el-select v-model="form.model_name" style="width: 100%">
          <el-option label="GPT-3.5 Turbo" value="gpt-3.5-turbo" />
          <el-option label="GPT-4o" value="gpt-4o" />
          <el-option label="GPT-4o Mini" value="gpt-4o-mini" />
        </el-select>
      </el-form-item>

      <el-form-item label="温度">
        <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input />
      </el-form-item>

      <el-form-item label="最大 Token">
        <el-input-number v-model="form.max_tokens" :min="256" :max="8192" :step="256" />
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
      <el-input v-model="form.system_prompt" type="textarea" :rows="8" />
    </el-form-item>

    <el-form-item label="模型">
      <el-select v-model="form.model_name" style="width: 100%">
        <el-option label="GPT-3.5 Turbo" value="gpt-3.5-turbo" />
        <el-option label="GPT-4o" value="gpt-4o" />
        <el-option label="GPT-4o Mini" value="gpt-4o-mini" />
      </el-select>
    </el-form-item>

    <el-form-item label="温度">
      <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input />
    </el-form-item>

    <el-form-item label="最大 Token">
      <el-input-number v-model="form.max_tokens" :min="256" :max="8192" :step="256" />
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

.inline-form {
  max-width: 720px;
}
</style>
