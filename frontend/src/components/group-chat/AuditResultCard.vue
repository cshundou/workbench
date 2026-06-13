<script setup lang="ts">
import { computed } from 'vue';

/** PPT 审核报告（与后端 ppt_audit_service 对齐） */
export interface PptAuditReview {
  passed?: boolean;
  total_score?: number;
  grade_label?: string;
  pass_threshold?: number;
  summary?: string;
  assignee?: string;
  audit_type?: string;
  dimension_scores?: Record<
    string,
    { label: string; score: number; max: number }
  >;
  issues?: string[];
  issue_details?: Array<{
    page?: number;
    issue?: string;
    suggestion?: string;
    assignee?: string;
  }>;
  suggestions?: string[];
}

const props = defineProps<{
  review: PptAuditReview;
}>();

const emit = defineEmits<{
  viewDetail: [];
}>();

const dimensions = computed(() => {
  const scores = props.review.dimension_scores || {};
  return Object.entries(scores).map(([key, val]) => ({
    key,
    label: val.label,
    score: val.score,
    max: val.max,
    percent: val.max ? Math.round((val.score / val.max) * 100) : 0,
  }));
});

const issueList = computed(() => {
  const details = props.review.issue_details;
  if (details?.length) return details;
  return (props.review.issues || []).map((issue) => ({ issue }));
});
</script>

<template>
  <div class="audit-card" :class="review.passed ? 'audit-card--pass' : 'audit-card--reject'">
    <div class="audit-card__header">
      <div class="audit-card__score">
        <span class="score-value">{{ review.total_score ?? '-' }}</span>
        <span class="score-unit">分</span>
      </div>
      <div class="audit-card__meta">
        <span class="grade">{{ review.grade_label || (review.passed ? '通过' : '不通过') }}</span>
        <span class="threshold">合格线 {{ review.pass_threshold ?? 80 }} 分</span>
      </div>
    </div>

    <p v-if="review.summary" class="audit-card__summary">{{ review.summary }}</p>

    <div v-if="dimensions.length" class="dimension-list">
      <div v-for="dim in dimensions" :key="dim.key" class="dimension-row">
        <span class="dim-label">{{ dim.label }}</span>
        <div class="dim-bar-wrap">
          <div class="dim-bar" :style="{ width: `${dim.percent}%` }" />
        </div>
        <span class="dim-score">{{ dim.score }}/{{ dim.max }}</span>
      </div>
    </div>

    <ul v-if="issueList.length" class="issue-list">
      <li v-for="(item, idx) in issueList.slice(0, 5)" :key="idx">
        <span v-if="item.page">P{{ item.page }} · </span>
        {{ item.issue }}
        <span v-if="item.assignee" class="assignee">→ {{ item.assignee }}</span>
      </li>
    </ul>

    <button type="button" class="detail-btn" @click="emit('viewDetail')">查看完整审核报告</button>
  </div>
</template>

<style scoped lang="scss">
.audit-card {
  margin-top: 10px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid $border-color;
  background: #fafbfc;

  &--pass {
    border-color: rgba(#52c41a, 0.35);
    background: #f6ffed;
  }

  &--reject {
    border-color: rgba(#f53f3f, 0.35);
    background: #fff2f0;
  }
}

.audit-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.audit-card__score {
  display: flex;
  align-items: baseline;
  gap: 2px;

  .score-value {
    font-size: 28px;
    font-weight: 700;
    color: $text-primary;
    line-height: 1;
  }

  .score-unit {
    font-size: 13px;
    color: $text-secondary;
  }
}

.audit-card__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .grade {
    font-size: 14px;
    font-weight: 600;
  }

  .threshold {
    font-size: 11px;
    color: $text-secondary;
  }
}

.audit-card__summary {
  margin: 8px 0 0;
  font-size: 12px;
  color: $text-secondary;
}

.dimension-list {
  margin-top: 10px;
}

.dimension-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 11px;
}

.dim-label {
  width: 72px;
  flex-shrink: 0;
  color: $text-secondary;
}

.dim-bar-wrap {
  flex: 1;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}

.dim-bar {
  height: 100%;
  background: $primary-color;
  border-radius: 3px;
}

.dim-score {
  width: 48px;
  text-align: right;
  color: $text-secondary;
}

.issue-list {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 11px;
  color: $text-primary;

  .assignee {
    color: $primary-color;
  }
}

.detail-btn {
  margin-top: 8px;
  padding: 0;
  border: none;
  background: none;
  font-size: 11px;
  color: $primary-color;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
}
</style>
