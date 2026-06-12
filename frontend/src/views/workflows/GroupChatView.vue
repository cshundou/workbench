<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, ChatDotRound } from '@element-plus/icons-vue';
import MemberList from '@/components/group-chat/MemberList.vue';
import MessageStream from '@/components/group-chat/MessageStream.vue';
import TaskProgress from '@/components/group-chat/TaskProgress.vue';
import ChatInput from '@/components/group-chat/ChatInput.vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import ApiKeyHintBanner from '@/components/settings/ApiKeyHintBanner.vue';
import { useGroupChatStore } from '@/stores/groupChat';
import { getKnowledgeBases } from '@/api/rag';

const route = useRoute();
const router = useRouter();
const groupChatStore = useGroupChatStore();

const workflowId = computed(() => {
  const id = route.params.id;
  return id ? Number(id) : undefined;
});

const sessionIdParam = computed(() => {
  const sid = route.query.session_id;
  return sid ? Number(sid) : undefined;
});

const taskInput = ref('');
const selectedKbId = ref<number | undefined>(undefined);
const kbOptions = ref<{ id: number; name: string }[]>([]);
const isStarting = ref(false);
const isSending = ref(false);
const streamRef = ref<HTMLElement | null>(null);

const showStartForm = computed(() => !groupChatStore.currentSession);
const sessionTitle = computed(() => groupChatStore.currentSession?.title || '虚拟项目群');

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'primary',
    reviewing: 'warning',
    completed: 'success',
    failed: 'danger',
    human_review: 'warning',
  };
  return map[groupChatStore.sessionStatus] || 'info';
});

async function loadKbOptions(): Promise<void> {
  const res = await getKnowledgeBases({ page: 1, page_size: 100 });
  kbOptions.value = res.items.map((kb) => ({ id: kb.id, name: kb.name }));
}

async function handleStart(): Promise<void> {
  if (!taskInput.value.trim()) {
    ElMessage.warning('请输入任务描述');
    return;
  }

  isStarting.value = true;
  groupChatStore.reset();

  try {
    const session = await groupChatStore.startSession({
      task: taskInput.value.trim(),
      workflow_id: workflowId.value,
      kb_id: selectedKbId.value,
    });
    router.replace({
      name: 'WorkflowGroupChat',
      params: route.params,
      query: { session_id: String(session.id) },
    });
    ElMessage.success('项目群已创建，Agent 团队开始协作');
  } catch (err) {
    console.error('[GroupChat] 启动失败', err);
  } finally {
    isStarting.value = false;
  }
}

const isHumanReview = computed(
  () => groupChatStore.sessionStatus === 'human_review',
);
const canCancel = computed(() =>
  ['pending', 'running', 'reviewing'].includes(groupChatStore.sessionStatus),
);

async function handleCancel(): Promise<void> {
  try {
    await groupChatStore.cancelSession();
    ElMessage.success('协作已取消');
  } catch (err) {
    console.error('[GroupChat] 取消失败', err);
    ElMessage.error('取消失败');
  }
}

async function handleResolve(action: 'approve' | 'reject'): Promise<void> {
  try {
    await groupChatStore.resolveReview(action);
    ElMessage.success(action === 'approve' ? '已批准交付' : '已驳回');
  } catch (err) {
    ElMessage.error('审核处理失败');
  }
}

async function handleSendMessage(content: string): Promise<void> {
  isSending.value = true;
  try {
    await groupChatStore.sendUserMessage(content);
  } catch (err) {
    console.error('[GroupChat] 发言失败', err);
    ElMessage.error('发言失败');
  } finally {
    isSending.value = false;
  }
}

function scrollToBottom(): void {
  nextTick(() => {
    if (streamRef.value) {
      streamRef.value.scrollTop = streamRef.value.scrollHeight;
    }
  });
}

watch(
  () => groupChatStore.messages.length,
  () => scrollToBottom(),
);

onMounted(async () => {
  await loadKbOptions();
  if (sessionIdParam.value) {
    await groupChatStore.loadSession(sessionIdParam.value);
  }
});

onUnmounted(() => {
  groupChatStore.disconnectWebSocket();
});
</script>

<template>
  <div class="group-chat-page">
    <div class="page-header">
      <el-button :icon="ArrowLeft" text @click="router.back()">返回</el-button>
      <SectionHeader
        :title="sessionTitle"
        :subtitle="groupChatStore.currentSession?.task_description"
      >
        <template #extra>
          <el-tag v-if="groupChatStore.currentSession" :type="statusTagType">
            {{ groupChatStore.sessionStatus }}
          </el-tag>
          <el-button
            v-if="canCancel"
            type="danger"
            plain
            size="small"
            @click="handleCancel"
          >
            停止协作
          </el-button>
        </template>
      </SectionHeader>
    </div>

    <ApiKeyHintBanner />

    <!-- 启动表单 -->
    <div v-if="showStartForm" class="start-panel">
      <div class="start-card">
        <div class="start-icon">
          <el-icon :size="48"><ChatDotRound /></el-icon>
        </div>
        <h2>创建虚拟项目群</h2>
        <p class="start-desc">
          提交复杂任务后，项目经理、研究员、工程师、分析师、审核员将在群内协同工作，全程透明可追溯。
        </p>
        <el-form label-position="top" class="start-form">
          <el-form-item label="任务描述" required>
            <el-input
              v-model="taskInput"
              type="textarea"
              :rows="4"
              placeholder="例如：帮我分析 Q2 销售数据并生成报告"
            />
          </el-form-item>
          <el-form-item label="知识库（可选）">
            <el-select
              v-model="selectedKbId"
              placeholder="选择知识库"
              clearable
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
          <el-button
            type="primary"
            size="large"
            :loading="isStarting"
            @click="handleStart"
          >
            启动项目群协作
          </el-button>
        </el-form>
      </div>
    </div>

    <!-- 三栏群聊界面 -->
    <div v-else class="chat-layout">
      <MemberList
        :members="groupChatStore.members"
        :typing-role="groupChatStore.typingRole"
      />

      <main class="chat-main">
        <el-alert
          v-if="isHumanReview"
          type="warning"
          title="需要人工审核"
          description="审核员已连续 3 次驳回，请批准或驳回本次交付。"
          show-icon
          class="human-review-banner"
        >
          <template #default>
            <div class="review-actions">
              <el-button type="success" size="small" @click="handleResolve('approve')">
                批准交付
              </el-button>
              <el-button type="danger" size="small" @click="handleResolve('reject')">
                驳回
              </el-button>
            </div>
          </template>
        </el-alert>
        <div ref="streamRef" class="stream-container">
          <MessageStream
            :messages="groupChatStore.messages"
            :typing-role="groupChatStore.typingRole"
          />
        </div>
        <ChatInput
          :disabled="groupChatStore.isCompleted"
          :loading="isSending"
          @send="handleSendMessage"
        />
      </main>

      <TaskProgress
        :progress="groupChatStore.progress"
        :steps="groupChatStore.progressSteps"
        :deliverables="groupChatStore.currentSession?.deliverables || []"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.group-chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  min-height: 600px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.start-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.start-card {
  max-width: 560px;
  width: 100%;
  padding: 40px;
  text-align: center;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);

  h2 {
    margin: 16px 0 8px;
    font-size: 22px;
    font-weight: 600;
    color: $text-primary;
  }
}

.start-icon {
  color: $primary-color;
}

.start-desc {
  color: $text-secondary;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 24px;
}

.start-form {
  text-align: left;
}

.chat-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 220px 1fr 240px;
  border: 1px solid $border-color;
  border-radius: 12px;
  overflow: hidden;
  background: $bg-white;
  min-height: 0;
}

.chat-main {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-left: 1px solid $border-color;
  border-right: 1px solid $border-color;
}

.stream-container {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.human-review-banner {
  margin: 12px 12px 0;
  flex-shrink: 0;
}

.review-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
</style>
