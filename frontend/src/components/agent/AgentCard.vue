<script setup lang="ts">
import { ChatDotRound, CopyDocument, Delete, Edit, Setting } from '@element-plus/icons-vue';
import type { AgentInfo } from '@/api/agent';

defineProps<{
  agent: AgentInfo;
  canWrite?: boolean;
  canDelete?: boolean;
}>();

const emit = defineEmits<{
  edit: [agent: AgentInfo];
  delete: [agent: AgentInfo];
  copy: [agent: AgentInfo];
  chat: [agent: AgentInfo];
  config: [agent: AgentInfo];
}>();
</script>

<template>
  <div class="agent-card">
    <div class="card-header flex-between">
      <h3 class="agent-name">{{ agent.name }}</h3>
      <el-tag v-if="agent.is_public" size="small" type="success">公开</el-tag>
      <el-tag v-else size="small" type="info">私有</el-tag>
    </div>

    <p class="agent-desc">{{ agent.description || '暂无描述' }}</p>

    <div class="agent-meta">
      <el-tag size="small" effect="plain">{{ agent.model_name }}</el-tag>
      <el-tag v-if="agent.tools.length" size="small" type="warning" effect="plain">
        {{ agent.tools.length }} 个工具
      </el-tag>
    </div>

    <div class="card-actions">
      <el-button type="primary" text :icon="ChatDotRound" @click="emit('chat', agent)">
        对话
      </el-button>
      <el-button text :icon="Setting" @click="emit('config', agent)">配置</el-button>
      <el-button v-if="canWrite" text :icon="Edit" @click="emit('edit', agent)">编辑</el-button>
      <el-button v-if="canWrite" text :icon="CopyDocument" @click="emit('copy', agent)">
        复制
      </el-button>
      <el-button
        v-if="canDelete"
        text
        type="danger"
        :icon="Delete"
        @click="emit('delete', agent)"
      >
        删除
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.agent-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  background: $bg-white;
  border: none;
  border-radius: $border-radius-lg;
  box-shadow: $shadow-card;
  transition: box-shadow 0.2s ease, transform 0.2s ease;

  &:hover {
    box-shadow: $shadow-card-hover;
    transform: translateY(-2px);
  }
}

.card-header {
  margin-bottom: 8px;
}

.agent-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.agent-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: $text-secondary;
  line-height: 1.5;
  min-height: 40px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.agent-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.card-actions {
  margin-top: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-top: 12px;
}
</style>
