<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  traceId?: string | null;
  org?: string;
  project?: string;
}>();

const traceUrl = computed(() => {
  if (!props.traceId) {
    return '';
  }
  const org = props.org || import.meta.env.VITE_LANGSMITH_ORG || '';
  const project = props.project || import.meta.env.VITE_LANGSMITH_PROJECT || 'ai-workbench';
  if (!org) {
    return `https://smith.langchain.com/public/${props.traceId}/r`;
  }
  return `https://smith.langchain.com/o/${org}/projects/p/${project}/r/${props.traceId}`;
});
</script>

<template>
  <a
    v-if="traceId && traceUrl"
    class="langsmith-trace-link"
    :href="traceUrl"
    target="_blank"
    rel="noopener noreferrer"
  >
    查看 LangSmith Trace
  </a>
</template>

<style scoped>
.langsmith-trace-link {
  font-size: 12px;
  color: var(--el-color-primary);
  text-decoration: none;
}
.langsmith-trace-link:hover {
  text-decoration: underline;
}
</style>
