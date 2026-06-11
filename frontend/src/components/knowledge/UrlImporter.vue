<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { importUrlDocument } from '@/api/rag';
import type { DocumentInfo } from '@/api/rag';

const props = defineProps<{
  kbId: number;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  imported: [doc: DocumentInfo];
}>();

const visible = ref(false);
const loading = ref(false);
const form = ref({ url: '', title: '' });

async function handleSubmit(): Promise<void> {
  if (!form.value.url.trim()) {
    ElMessage.warning('请输入 URL');
    return;
  }
  loading.value = true;
  try {
    const doc = await importUrlDocument(props.kbId, {
      url: form.value.url.trim(),
      title: form.value.title.trim() || undefined,
    });
    ElMessage.success('URL 导入成功，正在解析');
    emit('imported', doc);
    visible.value = false;
    form.value = { url: '', title: '' };
  } catch (error) {
    console.error('[URL Import Error]', error);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <el-button :disabled="disabled" @click="visible = true">导入链接</el-button>
  <el-dialog v-model="visible" title="从 URL 导入" width="480px" destroy-on-close>
    <el-form label-width="80px">
      <el-form-item label="URL" required>
        <el-input v-model="form.url" placeholder="https://example.com/docs" />
      </el-form-item>
      <el-form-item label="标题">
        <el-input v-model="form.title" placeholder="可选自定义标题" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">导入</el-button>
    </template>
  </el-dialog>
</template>
