<script setup lang="ts">
import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue';

withDefaults(
  defineProps<{
    content: string;
    streaming?: boolean;
  }>(),
  {
    streaming: false,
  },
);
</script>

<template>
  <MarkdownRenderer :content="content" :streaming="streaming" compact />
</template>
