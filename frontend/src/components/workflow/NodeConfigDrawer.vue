<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { getKnowledgeBases } from '@/api/rag';
import { getAgents, type AgentInfo } from '@/api/agent';
import { listSkills, type SkillInfo } from '@/api/plugins';
import type { WorkflowNodeDef } from '@/api/workflow';

const props = defineProps<{
  visible: boolean;
  node: WorkflowNodeDef | null;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  save: [node: WorkflowNodeDef];
}>();

const localConfig = ref<Record<string, unknown>>({});
const kbOptions = ref<{ id: number; name: string }[]>([]);
const agentOptions = ref<AgentInfo[]>([]);
const skillOptions = ref<SkillInfo[]>([]);

const drawerVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
});

watch(
  () => props.node,
  async (node) => {
    if (!node) return;
    localConfig.value = { ...(node.config || {}) };
    if (node.type === 'knowledge') {
      const res = await getKnowledgeBases({ page: 1, page_size: 100 });
      kbOptions.value = res.items.map((kb) => ({ id: kb.id, name: kb.name }));
    }
    if (node.type === 'custom_agent') {
      const res = await getAgents({ page: 1, page_size: 100 });
      agentOptions.value = res.items;
    }
    if (node.type === 'skill') {
      skillOptions.value = await listSkills(true);
    }
  },
  { immediate: true },
);

function handleSave(): void {
  if (!props.node) return;
  emit('save', {
    ...props.node,
    config: { ...localConfig.value },
  });
  drawerVisible.value = false;
}
</script>

<template>
  <el-drawer v-model="drawerVisible" :title="`节点配置：${node?.label || ''}`" size="400px">
    <template v-if="node">
      <el-form label-position="top">
        <el-form-item v-if="node.type === 'knowledge'" label="知识库（多选）">
          <el-select
            v-model="localConfig.kb_ids"
            multiple
            filterable
            placeholder="选择知识库"
            style="width: 100%"
          >
            <el-option
              v-for="kb in kbOptions"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
        </el-form-item>

        <template v-if="node.type === 'loop'">
          <el-form-item label="循环退出条件">
            <el-input
              v-model="localConfig.loop_condition"
              type="textarea"
              :rows="3"
              placeholder="例如：检索结果包含2024年"
            />
          </el-form-item>
          <el-form-item label="最大循环次数">
            <el-input-number
              v-model="localConfig.max_iterations"
              :min="1"
              :max="20"
              style="width: 100%"
            />
          </el-form-item>
        </template>

        <template v-if="node.type === 'scheduler' || node.type === 'reviewer'">
          <el-form-item label="Temperature（可选覆盖）">
            <el-slider
              v-model="localConfig.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              show-input
            />
          </el-form-item>
        </template>

        <el-form-item v-if="node.type === 'custom_agent'" label="绑定智能体">
          <el-select
            v-model="localConfig.agent_id"
            filterable
            placeholder="选择智能体"
            style="width: 100%"
          >
            <el-option
              v-for="agent in agentOptions"
              :key="agent.id"
              :label="agent.name"
              :value="agent.id"
            />
          </el-select>
        </el-form-item>

        <template v-if="node.type === 'audit'">
          <el-form-item label="最大审核重试次数">
            <el-input-number
              v-model="localConfig.max_review_retries"
              :min="1"
              :max="10"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="驳回打回目标节点 ID">
            <el-input v-model="localConfig.reject_target" placeholder="例如 scheduler" />
          </el-form-item>
        </template>

        <template v-if="node.type === 'skill'">
          <el-form-item label="Skill Key">
            <el-select
              v-model="localConfig.skill_key"
              filterable
              placeholder="选择已启用 Skill"
              style="width: 100%"
            >
              <el-option
                v-for="skill in skillOptions"
                :key="skill.skill_key"
                :label="`${skill.name} (${skill.skill_key})`"
                :value="skill.skill_key"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="任务描述（可选覆盖）">
            <el-input
              v-model="localConfig.task"
              type="textarea"
              :rows="2"
              placeholder="留空则使用工作流全局任务"
            />
          </el-form-item>
        </template>

        <el-form-item v-if="node.type === 'condition'" label="默认分支目标节点 ID">
          <el-input v-model="localConfig.default_target" placeholder="节点 id" />
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="handleSave">保存配置</el-button>
    </template>
  </el-drawer>
</template>
