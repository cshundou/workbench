<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { GroupChatMember } from '@/api/groupChat';

const props = defineProps<{
  members: GroupChatMember[];
  typingRole?: string | null;
  progress?: number;
  isForming?: boolean;
  selectedRole?: string | null;
}>();

const emit = defineEmits<{
  selectMember: [role: string];
}>();

const visibleMembers = ref<GroupChatMember[]>([]);
const formationDone = ref(false);

watch(
  () => props.members,
  (newMembers) => {
    if (!props.isForming) {
      visibleMembers.value = newMembers;
      formationDone.value = true;
      return;
    }
    // 团队组建入场动画：成员逐个加入
    visibleMembers.value = [];
    formationDone.value = false;
    newMembers.forEach((member, idx) => {
      setTimeout(() => {
        visibleMembers.value.push(member);
        if (idx === newMembers.length - 1) {
          formationDone.value = true;
        }
      }, idx * 300);
    });
  },
  { immediate: true },
);

const statusLabel: Record<string, string> = {
  pending: '待开始',
  thinking: '思考中…',
  working: '执行中…',
  completed: '已完成',
  error: '异常',
  revision: '待修改',
  idle: '在线',
};

const roleDisplayNames: Record<string, string> = {
  copywriter: '文案策划师',
  ppt_designer: 'PPT设计师',
  data_visualizer: '数据可视化设计师',
};

function memberStatus(member: GroupChatMember): string {
  if (props.typingRole === member.role) {
    if (member.role === 'ppt_designer') {
      return '排版生成中…';
    }
    return member.role === 'project_manager' ? '思考中…' : '执行中…';
  }
  if (member.is_auditor && member.review_round) {
    return `最终审核 · 第 ${member.review_round} 轮`;
  }
  return statusLabel[member.status] || member.status;
}

function statusClass(member: GroupChatMember): string {
  const status = props.typingRole === member.role ? 'working' : member.status;
  return `status--${status}`;
}

function taskProgress(member: GroupChatMember): string {
  if (member.status === 'pending' && member.current_task) {
    return `等待依赖：${member.current_task}`;
  }
  if (member.completed_count !== undefined && member.total_count) {
    return `${member.completed_count}/${member.total_count} 项已完成`;
  }
  return '';
}

const teamTitle = computed(() => {
  const count = props.members.length;
  return count ? `项目团队（${count}人）` : '项目团队';
});

function displayMemberName(member: GroupChatMember): string {
  return member.name || roleDisplayNames[member.role] || member.role;
}

function handleClick(member: GroupChatMember): void {
  emit('selectMember', member.role);
}
</script>

<template>
  <aside class="member-panel">
    <div class="panel-header">
      <h3 class="panel-title">🧑‍🤝‍🧑 {{ teamTitle }}</h3>
      <div v-if="formationDone" class="progress-bar-wrap">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${progress ?? 0}%` }" />
        </div>
        <span class="progress-text">{{ Math.round(progress ?? 0) }}%</span>
      </div>
      <div v-else class="forming-hint">正在为您组建专属团队…</div>
    </div>

    <ul class="member-list">
      <li
        v-for="(member, idx) in visibleMembers"
        :key="member.role"
        class="member-item member-enter"
        :class="{
          'member-item--active': typingRole === member.role,
          'member-item--selected': selectedRole === member.role,
          'member-item--auditor': member.is_auditor && member.status !== 'revision',
          'member-item--auditor-active':
            member.is_auditor &&
            (member.review_round || typingRole === member.role),
          'member-item--revision': member.status === 'revision',
          'member-item--human-review': member.is_auditor && member.status === 'error',
        }"
        :style="{ animationDelay: `${idx * 0.1}s` }"
        @click="handleClick(member)"
      >
        <span class="member-avatar" :style="{ background: member.color + '18' }">
          {{ member.avatar }}
        </span>
        <div class="member-info">
          <span class="member-name">{{ displayMemberName(member) }}</span>
          <span class="member-status" :class="statusClass(member)">
            <span class="status-dot" :class="statusClass(member)" />
            {{ memberStatus(member) }}
          </span>
          <span v-if="member.current_task" class="member-task" :title="member.current_task">
            当前：{{ member.current_task }}
          </span>
          <span v-if="member.reject_reason" class="member-reject">
            打回：{{ member.reject_reason }}
          </span>
          <span v-if="taskProgress(member)" class="member-count">
            {{ taskProgress(member) }}
          </span>
        </div>
      </li>
    </ul>
  </aside>
</template>

<style lang="scss" scoped>
.member-panel {
  height: 100%;
  padding: 16px 12px;
  border-right: 1px solid $border-color;
  background: $bg-white;
  overflow-y: auto;
}

.panel-header {
  margin-bottom: 12px;
}

.panel-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
}

.progress-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: $border-color;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: $primary-color;
  border-radius: 2px;
  transition: width 0.4s ease;
}

.progress-text {
  font-size: 11px;
  color: $text-secondary;
  min-width: 32px;
}

.forming-hint {
  font-size: 12px;
  color: $primary-color;
  animation: pulse 1.5s infinite;
}

.member-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.member-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 8px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;

  &--active {
    background: rgba($primary-color, 0.06);
  }

  &--selected {
    background: rgba($primary-color, 0.1);
    border-color: rgba($primary-color, 0.3);
  }

  &--auditor-active {
    border-color: #ff7d00;
    box-shadow: 0 0 0 1px rgba(#ff7d00, 0.3);
  }

  &--revision {
    border-color: #f53f3f;
    background: rgba(#f53f3f, 0.04);
  }

  &--human-review {
    border-color: #f53f3f;
    background: rgba(#f53f3f, 0.08);
  }
}

.member-enter {
  animation: slideIn 0.35s ease both;
}

.member-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 18px;
  flex-shrink: 0;
}

.member-info {
  flex: 1;
  min-width: 0;
}

.member-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: $text-primary;
}

.member-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: $text-secondary;
  margin-top: 2px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;

  &.status--pending {
    background: #c9cdd4;
  }

  &.status--thinking {
    background: #f7ba1e;
    animation: blink 1s infinite;
  }

  &.status--working {
    background: $primary-color;
    animation: breathe 1.5s infinite;
  }

  &.status--completed {
    background: #00b42a;
  }

  &.status--error,
  &.status--revision {
    background: #f53f3f;
  }
}

.member-task {
  display: block;
  font-size: 11px;
  color: $text-secondary;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-reject {
  display: block;
  font-size: 11px;
  color: #f53f3f;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-count {
  display: block;
  font-size: 10px;
  color: $text-secondary;
  margin-top: 2px;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes blink {
  0%,
  100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}

@keyframes breathe {
  0%,
  100% {
    opacity: 0.5;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.1);
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
}
</style>
