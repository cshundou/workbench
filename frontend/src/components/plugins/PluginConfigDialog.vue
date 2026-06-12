<script setup lang="ts">
import { ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { updatePluginConfig } from '@/api/plugins';

const props = defineProps<{
  visible: boolean;
  pluginId: string;
  pluginName: string;
  initialConfig: Record<string, unknown>;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  saved: [];
}>();

const configJson = ref('{}');
const saving = ref(false);

watch(
  () => props.visible,
  (open) => {
    if (open) {
      configJson.value = JSON.stringify(props.initialConfig || {}, null, 2);
    }
  },
);

async function handleSave(): Promise<void> {
  saving.value = true;
  try {
    const config = JSON.parse(configJson.value) as Record<string, unknown>;
    await updatePluginConfig(props.pluginId, config);
    ElMessage.success('配置已保存');
    emit('saved');
    emit('update:visible', false);
  } catch (err) {
    ElMessage.error('配置格式错误或保存失败');
    console.error(err);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="`${pluginName} - 配置`"
    width="520px"
    @update:model-value="emit('update:visible', $event)"
  >
    <el-input v-model="configJson" type="textarea" :rows="10" />
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>
