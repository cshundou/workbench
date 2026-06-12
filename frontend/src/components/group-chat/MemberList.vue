<script setup lang="ts">
import { computed } from 'vue';
import type { GroupChatMember } from '@/api/groupChat';

const props = defineProps<{
  members: GroupChatMember[];
  typingRole?: string | null;
}>();

const statusLabel: Record<string, string> = {
  idle: '在线',
  thinking: '思考中...',
  working: '执行中...',
};

function memberStatus(member: GroupChatMember): string {
  if (props.typingRole === member.role) {
    return member.role === 'project_manager' ? '思考中...' : '执行中...';
  }
  return statusLabel[member.status] || member.status;
}

const sortedMembers = computed(() => {
  const order = ['project_manager', 'researcher', 'engineer', 'analyst', 'auditor'];
  return [...props.members].sort(
    (a, b) => order.indexOf(a.role) - order.indexOf(b.role),
  );
});
</script>

<template>
  <aside class="member-panel">
    <h3 class="panel-title">项目群成员</h3>
    <ul class="member-list">
      <li
        v-for="member in sortedMembers"
        :key="member.role"
        class="member-item"
        :class="{ 'member-item--active': typingRole === member.role }"
      >
        <span class="member-avatar" :style="{ background: member.color + '18' }">
          {{ member.avatar }}
        </span>
        <div class="member-info">
          <span class="member-name">{{ member.name }}</span>
          <span
            class="member-status"
            :class="{ 'member-status--active': typingRole === member.role }"
          >
            {{ memberStatus(member) }}
          </span>
        </div>
        <span
          v-if="typingRole === member.role"
          class="thinking-dots"
          aria-label="正在工作"
        >
          <span /><span /><span />
        </span>
      </li>
    </ul>
  </aside>
</template>

<style lang="scss" scoped>
.member-panel {
  height: 100%;
  padding: 20px 16px;
  border-right: 1px solid $border-color;
  background: $bg-white;
}

.panel-title {
  margin: 0 0 16px;
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
}

.member-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
  border-radius: 8px;
  transition: background 0.2s;

  &--active {
    background: rgba($primary-color, 0.06);
  }
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
  display: block;
  font-size: 11px;
  color: $text-secondary;
  margin-top: 2px;

  &--active {
    color: $primary-color;
  }
}

.thinking-dots {
  display: flex;
  gap: 3px;

  span {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: $primary-color;
    animation: blink 1.2s infinite;

    &:nth-child(2) {
      animation-delay: 0.2s;
    }

    &:nth-child(3) {
      animation-delay: 0.4s;
    }
  }
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.3;
  }
  40% {
    opacity: 1;
  }
}
</style>
