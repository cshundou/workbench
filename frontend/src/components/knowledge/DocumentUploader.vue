<script setup lang="ts">
import { ref } from 'vue';
import { UploadFilled } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { uploadDocument } from '@/api/rag';
import type { DocumentInfo } from '@/api/rag';

const props = defineProps<{
  kbId: number;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  uploaded: [doc: DocumentInfo];
  'all-done': [];
}>();

const uploading = ref(false);
const uploadProgress = ref<Record<string, number>>({});

/** 支持的文件类型 */
const acceptTypes = '.pdf,.doc,.docx,.txt,.md,.html,.xlsx,.xls,.csv';

/** 批量上传文件 */
async function handleUpload(files: File[]): Promise<void> {
  if (props.disabled || files.length === 0) {
    return;
  }

  uploading.value = true;

  try {
    for (const file of files) {
      const fileKey = `${file.name}-${file.size}`;
      uploadProgress.value[fileKey] = 0;

      try {
        const doc = await uploadDocument(props.kbId, file, undefined, (percent) => {
          uploadProgress.value[fileKey] = percent;
        });
        emit('uploaded', doc);
        ElMessage.success(`「${file.name}」上传成功`);
      } catch (error) {
        console.error(`[Upload Error] ${file.name}`, error);
        ElMessage.error(`「${file.name}」上传失败`);
      } finally {
        delete uploadProgress.value[fileKey];
      }
    }
    emit('all-done');
  } finally {
    uploading.value = false;
  }
}

/** el-upload 自定义上传 */
async function customUpload(options: { file: File }): Promise<void> {
  await handleUpload([options.file]);
}

/** 拖拽放下时处理多文件 */
function handleDrop(event: DragEvent): void {
  const files = Array.from(event.dataTransfer?.files || []);
  if (files.length > 0) {
    handleUpload(files);
  }
}
</script>

<template>
  <div class="document-uploader" @drop.prevent="handleDrop" @dragover.prevent>
    <el-upload
      drag
      multiple
      :accept="acceptTypes"
      :show-file-list="false"
      :disabled="disabled || uploading"
      :http-request="customUpload"
      class="upload-area"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="upload-text">
        将文件拖到此处，或 <em>点击上传</em>
      </div>
      <template #tip>
        <div class="upload-tip">
          支持 PDF、Word、Excel、TXT、Markdown 等格式，可批量上传
        </div>
      </template>
    </el-upload>

    <div v-if="Object.keys(uploadProgress).length > 0" class="upload-progress-list">
      <div
        v-for="(percent, fileKey) in uploadProgress"
        :key="fileKey"
        class="progress-item"
      >
        <span class="file-name">{{ fileKey.split('-')[0] }}</span>
        <el-progress :percentage="percent" :stroke-width="6" />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.document-uploader {
  width: 100%;
}

.upload-area {
  width: 100%;

  :deep(.el-upload) {
    width: 100%;
  }

  :deep(.el-upload-dragger) {
    width: 100%;
    padding: 32px 20px;
  }
}

.upload-icon {
  font-size: 48px;
  color: $primary-color;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  color: $text-primary;

  em {
    color: $primary-color;
    font-style: normal;
  }
}

.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  color: $text-secondary;
  text-align: center;
}

.upload-progress-list {
  margin-top: 16px;
}

.progress-item {
  margin-bottom: 8px;

  .file-name {
    display: block;
    font-size: 13px;
    color: $text-secondary;
    margin-bottom: 4px;
  }
}
</style>
