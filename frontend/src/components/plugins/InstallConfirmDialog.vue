<script setup lang="ts">
import { computed } from 'vue';
import { CATEGORY_LABELS } from '@/constants/pluginPermissions';

const props = defineProps<{
  visible: boolean;
  pluginName: string;
  permissions: string[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  confirm: [];
}>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
});

function permissionLabel(perm: string): string {
  return CATEGORY_LABELS[perm] || perm;
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="安装确认"
    width="480px"
    :close-on-click-modal="false"
  >
    <p>即将安装 <strong>{{ pluginName }}</strong>，该插件需要以下权限：</p>
    <ul class="perm-list">
      <li v-for="perm in permissions" :key="perm">{{ permissionLabel(perm) }}</li>
    </ul>
    <p class="hint">安装后可在「已安装插件」中配置或禁用。</p>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="emit('confirm')">
        确认安装
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.perm-list {
  margin: 12px 0;
  padding-left: 20px;
  color: #606266;
}
.hint {
  font-size: 13px;
  color: #909399;
}
</style>
