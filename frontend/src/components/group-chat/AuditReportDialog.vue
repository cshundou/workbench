<script setup lang="ts">
import type { PptAuditReview } from './AuditResultCard.vue';

defineProps<{
  visible: boolean;
  review: PptAuditReview | null;
}>();

const emit = defineEmits<{
  close: [];
}>();
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="PPT 质量审核报告"
    width="560px"
    destroy-on-close
    @update:model-value="(v: boolean) => !v && emit('close')"
  >
    <template v-if="review">
      <el-descriptions :column="2" border class="mb-4">
        <el-descriptions-item label="综合得分">
          {{ review.total_score ?? '-' }} 分（{{ review.grade_label || '-' }}）
        </el-descriptions-item>
        <el-descriptions-item label="审核类型">
          {{ review.audit_type === 'outline' ? '大纲审核' : review.audit_type === 'content' ? '内容审核' : '终稿审核' }}
        </el-descriptions-item>
        <el-descriptions-item label="结论" :span="2">
          {{ review.passed ? '通过' : '不通过' }}
        </el-descriptions-item>
        <el-descriptions-item label="摘要" :span="2">
          {{ review.summary || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <h4 class="section-title">五维分项得分</h4>
      <el-table
        v-if="review.dimension_scores"
        :data="Object.entries(review.dimension_scores).map(([k, v]) => ({ key: k, ...v }))"
        size="small"
        stripe
      >
        <el-table-column prop="label" label="维度" />
        <el-table-column prop="score" label="得分" width="80" />
        <el-table-column prop="max" label="满分" width="80" />
      </el-table>

      <h4 v-if="review.issue_details?.length || review.issues?.length" class="section-title">
        问题清单
      </h4>
      <el-table
        v-if="review.issue_details?.length"
        :data="review.issue_details"
        size="small"
        stripe
      >
        <el-table-column prop="page" label="页码" width="60" />
        <el-table-column prop="issue" label="问题" min-width="140" />
        <el-table-column prop="suggestion" label="修改建议" min-width="120" />
        <el-table-column prop="assignee" label="责任人" width="100" />
      </el-table>
      <ul v-else-if="review.issues?.length" class="plain-issues">
        <li v-for="(issue, idx) in review.issues" :key="idx">{{ issue }}</li>
      </ul>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.mb-4 {
  margin-bottom: 16px;
}

.section-title {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
}

.plain-issues {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
}
</style>
