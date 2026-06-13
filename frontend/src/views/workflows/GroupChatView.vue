<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, ChatDotRound, Top } from '@element-plus/icons-vue';
import MemberList from '@/components/group-chat/MemberList.vue';
import MessageStream from '@/components/group-chat/MessageStream.vue';
import TaskProgress from '@/components/group-chat/TaskProgress.vue';
import ChatInput from '@/components/group-chat/ChatInput.vue';
import TeamAdjustDialog from '@/components/group-chat/TeamAdjustDialog.vue';
import ReportViewer from '@/components/group-chat/ReportViewer.vue';
import type { TeamConfig } from '@/api/agentRoles';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import ApiKeyHintBanner from '@/components/settings/ApiKeyHintBanner.vue';
import ErrorAdvicePanel from '@/components/common/ErrorAdvicePanel.vue';
import { useGroupChatStore } from '@/stores/groupChat';
import { getGroupChatAuditLogs } from '@/api/groupChat';
import { getKnowledgeBases } from '@/api/rag';
import type { Deliverable } from '@/utils/deliverables';

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
const showTeamAdjust = ref(false);
const pendingTeamConfig = ref<TeamConfig | null>(null);
const useClassicFive = ref(false);

/** 滚动控制 */
const isNearBottom = ref(true);
const showNewMessageHint = ref(false);
const showBackToTop = ref(false);
const highlightMessageId = ref<string | null>(null);

/** 报告查看器 */
const reportVisible = ref(false);
const activeDeliverable = ref<Deliverable | null>(null);

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
      team_config: pendingTeamConfig.value || undefined,
      use_classic_five: useClassicFive.value,
      template_id: pendingTeamConfig.value?.template_id,
    });
    pendingTeamConfig.value = null;
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
const isFailed = computed(() => groupChatStore.sessionStatus === 'failed');
const sessionError = computed(
  () => groupChatStore.currentSession?.error_message || '协作执行失败，请查看后端日志或重试',
);

const errorSuggestions = computed(
  () => groupChatStore.currentSession?.error_suggestions || [],
);

const rawError = computed(() => groupChatStore.currentSession?.raw_error || null);

const isRestarting = ref(false);
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

async function handleExportAuditLogs(): Promise<void> {
  if (!groupChatStore.currentSession) return;
  try {
    const data = await getGroupChatAuditLogs(groupChatStore.currentSession.id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `group-chat-audit-${groupChatStore.currentSession.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
    ElMessage.success('审计日志已导出');
  } catch (err) {
    console.error('[GroupChat] 审计导出失败', err);
    ElMessage.error('审计日志导出失败');
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
    if (isFailed.value) {
      await groupChatStore.sendUserMessage(content, false);
      ElMessage.success('补充说明已记录，可点击「重新执行」继续协作');
    } else {
      await groupChatStore.sendUserMessage(content);
    }
  } catch (err) {
    console.error('[GroupChat] 发言失败', err);
    ElMessage.error('发言失败');
  } finally {
    isSending.value = false;
  }
}

async function handleRestart(): Promise<void> {
  isRestarting.value = true;
  try {
    await groupChatStore.restartSession();
    ElMessage.success('已重新启动协作');
  } catch (err) {
    console.error('[GroupChat] 重启失败', err);
    ElMessage.error('重新执行失败');
  } finally {
    isRestarting.value = false;
  }
}

async function handleRestartWithLastInput(): Promise<void> {
  isRestarting.value = true;
  try {
    await groupChatStore.restartSession();
    ElMessage.success('已重新启动协作');
  } catch (err) {
    ElMessage.error('重新执行失败');
  } finally {
    isRestarting.value = false;
  }
}

function checkScrollPosition(): void {
  const el = streamRef.value;
  if (!el) return;
  const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  isNearBottom.value = distanceFromBottom < 80;
  showBackToTop.value = el.scrollTop > 300;
  if (isNearBottom.value) {
    showNewMessageHint.value = false;
  }
}

function scrollToBottom(smooth = false): void {
  nextTick(() => {
    if (streamRef.value) {
      streamRef.value.scrollTo({
        top: streamRef.value.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto',
      });
      showNewMessageHint.value = false;
      isNearBottom.value = true;
    }
  });
}

function scrollToTop(): void {
  streamRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
}

function locateMessage(messageId: string): void {
  highlightMessageId.value = messageId;
  nextTick(() => {
    const el = document.getElementById(`msg-${messageId}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => {
      highlightMessageId.value = null;
    }, 2000);
  });
}

function openReport(deliverable: Deliverable | (Partial<Deliverable> & { content: string; name: string })): void {
  activeDeliverable.value = {
    id: deliverable.id || deliverable.messageId || 'report',
    messageId: deliverable.messageId || deliverable.id || '',
    name: deliverable.name,
    category: deliverable.category || 'intermediate',
    type: deliverable.type || 'text',
    fileType: deliverable.fileType || 'md',
    content: deliverable.content,
    createdBy: deliverable.createdBy || '',
    createdAt: deliverable.createdAt || new Date().toISOString(),
    size: deliverable.size || new Blob([deliverable.content]).size,
    chartConfig: deliverable.chartConfig,
  };
  reportVisible.value = true;
}

/** 进度步骤点击跳转到对应阶段首条消息 */
function jumpToPhase(stepKey: string): void {
  const phaseMap: Record<string, string[]> = {
    start: ['task_start'],
    execute: ['task_assignment', 'progress_update', 'result_delivery', 'answer'],
    review: ['review_request', 'review_result'],
    complete: ['task_complete'],
  };
  const types = phaseMap[stepKey];
  if (!types) return;
  const msg = groupChatStore.messages.find((m) => types.includes(m.type));
  if (msg) locateMessage(msg.id);
}

watch(
  () => groupChatStore.messages.length,
  (newLen, oldLen) => {
    if (newLen > oldLen) {
      if (isNearBottom.value) {
        scrollToBottom();
      } else {
        showNewMessageHint.value = true;
      }
    }
  },
);

onMounted(async () => {
  await loadKbOptions();
  if (sessionIdParam.value) {
    await groupChatStore.loadSession(sessionIdParam.value);
    scrollToBottom();
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
            v-if="groupChatStore.currentSession"
            plain
            size="small"
            @click="handleExportAuditLogs"
          >
            导出审计
          </el-button>
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

    <ApiKeyHintBanner scene="workflow" />

    <!-- 启动表单 -->
    <div v-if="showStartForm" class="start-panel">
      <div class="start-card">
        <div class="start-icon">
          <el-icon :size="48"><ChatDotRound /></el-icon>
        </div>
        <h2>创建虚拟项目群</h2>
        <p class="start-desc">
          提交任务后，系统将智能分析并组建专属项目团队（2-8 人），动态分工协同执行，全程透明可追溯。
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
          <div class="start-actions">
            <el-button size="large" @click="showTeamAdjust = true">调整团队</el-button>
            <el-button
              type="primary"
              size="large"
              :loading="isStarting"
              @click="handleStart"
            >
              启动项目群协作
            </el-button>
          </div>
          <el-checkbox v-model="useClassicFive" class="classic-checkbox">
            使用经典五角色模式
          </el-checkbox>
        </el-form>
        <TeamAdjustDialog
          v-model:visible="showTeamAdjust"
          :task="taskInput"
          :initial-config="pendingTeamConfig"
          @confirm="(cfg) => { pendingTeamConfig = cfg; }"
        />
      </div>
    </div>

    <!-- 三栏群聊界面 -->
    <div v-else class="chat-layout">
      <MemberList
        :members="groupChatStore.members"
        :typing-role="groupChatStore.typingRole"
        :progress="groupChatStore.progress"
        :is-forming="groupChatStore.isFormingTeam"
        :selected-role="groupChatStore.selectedRole"
        @select-member="groupChatStore.selectMember"
      />

      <main class="chat-main">
        <ErrorAdvicePanel
          v-if="isFailed"
          :message="sessionError"
          :suggestions="errorSuggestions"
          :raw-error="rawError"
          class="human-review-banner"
          @retry="handleRestart"
        />
        <div v-if="isFailed" class="failed-actions">
          <el-button type="primary" :loading="isRestarting" @click="handleRestart">
            重新执行
          </el-button>
          <el-button :loading="isRestarting" @click="handleRestartWithLastInput">
            使用当前任务重试
          </el-button>
        </div>
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
        <div ref="streamRef" class="stream-container" @scroll="checkScrollPosition">
          <MessageStream
            :messages="groupChatStore.messages"
            :typing-role="groupChatStore.typingRole"
            :filter-role="groupChatStore.selectedRole"
            :highlight-message-id="highlightMessageId"
            @view-report="openReport"
          />
        </div>

        <!-- 滚动辅助按钮 -->
        <Transition name="fade">
          <button
            v-if="showNewMessageHint"
            type="button"
            class="scroll-hint-btn"
            @click="scrollToBottom(true)"
          >
            新消息 ↓
          </button>
        </Transition>
        <Transition name="fade">
          <button
            v-if="showBackToTop"
            type="button"
            class="back-top-btn"
            @click="scrollToTop"
          >
            <el-icon><Top /></el-icon>
          </button>
        </Transition>

        <ChatInput
          :disabled="!groupChatStore.canSendMessage"
          :loading="isSending"
          :placeholder="
            isFailed
              ? '输入补充说明或修改要求（发送后可重新执行）'
              : undefined
          "
          @send="handleSendMessage"
        />
      </main>

      <TaskProgress
        :progress="groupChatStore.progress"
        :steps="groupChatStore.progressSteps"
        :messages="groupChatStore.messages"
        :deliverables="groupChatStore.currentSession?.deliverables || []"
        @view-deliverable="openReport"
        @locate-message="locateMessage"
        @jump-phase="jumpToPhase"
      />
    </div>

    <ReportViewer
      v-model:visible="reportVisible"
      :deliverable="activeDeliverable"
    />
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

.start-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.classic-checkbox {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}

.chat-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 220px 1fr 260px;
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
  position: relative;
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

.failed-actions {
  display: flex;
  gap: 8px;
  padding: 0 12px 8px;
  flex-shrink: 0;
}

.review-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.scroll-hint-btn {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 16px;
  font-size: 13px;
  color: $primary-color;
  background: $bg-white;
  border: 1px solid rgba($primary-color, 0.4);
  border-radius: 20px;
  cursor: pointer;
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

  &:hover {
    background: rgba($primary-color, 0.06);
  }
}

.back-top-btn {
  position: absolute;
  bottom: 80px;
  right: 16px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $text-secondary;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 50%;
  cursor: pointer;
  z-index: 10;

  &:hover {
    color: $primary-color;
    border-color: rgba($primary-color, 0.4);
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 1024px) {
  .chat-layout {
    grid-template-columns: 180px 1fr 220px;
  }
}

@media (max-width: 768px) {
  .chat-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }
}
</style>
