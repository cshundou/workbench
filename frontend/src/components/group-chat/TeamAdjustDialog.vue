<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  buildTeam,
  listProfessionalRoles,
  listTeamTemplates,
  type ProfessionalRole,
  type TeamConfig,
  type TeamMemberConfig,
  type TeamTemplateItem,
} from '@/api/agentRoles';

const props = defineProps<{
  visible: boolean;
  task: string;
  initialConfig?: TeamConfig | null;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  confirm: [config: TeamConfig];
}>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
});

const loading = ref(false);
const roles = ref<ProfessionalRole[]>([]);
const templates = ref<TeamTemplateItem[]>([]);
const members = ref<TeamMemberConfig[]>([]);
const selectedTemplate = ref<string>('');

async function loadData(): Promise<void> {
  loading.value = true;
  try {
    const [roleList, tplData] = await Promise.all([
      listProfessionalRoles(),
      listTeamTemplates(),
    ]);
    roles.value = roleList;
    templates.value = [...tplData.official, ...tplData.custom];
    if (props.initialConfig?.members?.length) {
      members.value = [...props.initialConfig.members];
    } else if (props.task) {
      const config = await buildTeam({ task: props.task });
      members.value = [...config.members];
    }
  } catch (err) {
    console.error('[TeamAdjust] 加载失败', err);
    ElMessage.error('加载团队配置失败');
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) loadData();
  },
);

async function handleTemplateChange(templateId: string): Promise<void> {
  if (!templateId || !props.task) return;
  try {
    const config = await buildTeam({ task: props.task, template_id: templateId });
    members.value = [...config.members];
  } catch (err) {
    ElMessage.error('套用模板失败');
  }
}

function addMember(role: ProfessionalRole): void {
  if (members.value.some((m) => m.role_id === role.role_id)) {
    ElMessage.warning('该角色已在团队中');
    return;
  }
  members.value.push({
    role_id: role.role_id,
    name: role.name,
    avatar: role.avatar,
    responsibility: role.responsibility,
    tools: role.tools,
    color: role.color,
    subtasks: [],
  });
}

function removeMember(index: number): void {
  const roleId = members.value[index]?.role_id;
  if (roleId === 'auditor') {
    const auditorCount = members.value.filter((m) => m.role_id === 'auditor').length;
    if (auditorCount <= 1) {
      ElMessage.warning('团队至少需要 1 名审核员');
      return;
    }
  }
  members.value.splice(index, 1);
}

function handleConfirm(): void {
  if (members.value.length < 2) {
    ElMessage.warning('团队至少需要 2 名成员');
    return;
  }
  const hasAuditor = members.value.some(
    (m) => m.role_id === 'auditor' || m.role_id === 'compliance_officer',
  );
  if (!hasAuditor) {
    ElMessage.warning('团队必须包含至少 1 名审核员');
    return;
  }
  const config: TeamConfig = {
    team_id: props.initialConfig?.team_id || `team_${Date.now()}`,
    task_description: props.task,
    team_size: members.value.length,
    members: members.value,
    workflow: members.value.map((m) => m.role_id).join(' → '),
    max_review_rounds: 3,
    template_id: selectedTemplate.value || 'custom',
  };
  emit('confirm', config);
  dialogVisible.value = false;
}

const customRoles = computed(() => roles.value.filter((r) => !r.is_preset));
const presetRoles = computed(() => roles.value.filter((r) => r.is_preset));
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="调整团队"
    width="720px"
    destroy-on-close
  >
    <div v-loading="loading" class="adjust-dialog">
      <el-form label-position="top">
        <el-form-item label="套用模板">
          <el-select
            v-model="selectedTemplate"
            placeholder="选择团队模板"
            clearable
            style="width: 100%"
            @change="handleTemplateChange"
          >
            <el-option
              v-for="tpl in templates"
              :key="String(tpl.id)"
              :label="tpl.name"
              :value="String(tpl.id)"
            >
              <span>{{ tpl.name }}</span>
              <span class="tpl-desc">{{ tpl.description }}</span>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>

      <div class="section-title">当前团队成员（{{ members.length }} 人）</div>
      <ul class="member-edit-list">
        <li v-for="(member, idx) in members" :key="member.role_id + idx" class="member-edit-item">
          <span class="member-avatar">{{ member.avatar }}</span>
          <div class="member-edit-info">
            <el-input v-model="member.name" size="small" placeholder="角色名称" />
            <el-input
              v-model="member.responsibility"
              size="small"
              placeholder="职责描述"
              class="mt-4"
            />
          </div>
          <el-button type="danger" text size="small" @click="removeMember(idx)">
            移除
          </el-button>
        </li>
      </ul>

      <div class="section-title">从角色库添加</div>
      <div class="role-chips">
        <el-tag
          v-for="role in presetRoles"
          :key="role.role_id"
          class="role-chip"
          effect="plain"
          @click="addMember(role)"
        >
          {{ role.avatar }} {{ role.name }}
        </el-tag>
      </div>
      <div v-if="customRoles.length" class="role-chips custom">
        <el-tag
          v-for="role in customRoles"
          :key="role.role_id"
          type="success"
          class="role-chip"
          effect="plain"
          @click="addMember(role)"
        >
          {{ role.avatar }} {{ role.name }}
        </el-tag>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm">确认团队</el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.adjust-dialog {
  min-height: 200px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
  margin: 16px 0 8px;
}

.member-edit-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.member-edit-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px;
  border: 1px solid $border-color;
  border-radius: 8px;
  margin-bottom: 8px;
}

.member-avatar {
  font-size: 24px;
  flex-shrink: 0;
}

.member-edit-info {
  flex: 1;
}

.mt-4 {
  margin-top: 4px;
}

.role-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  &.custom {
    margin-top: 8px;
  }
}

.role-chip {
  cursor: pointer;
}

.tpl-desc {
  margin-left: 8px;
  font-size: 12px;
  color: $text-secondary;
}
</style>
