import { test, expect } from '@playwright/test';

test.describe('知识库模块', () => {
  test('登录页可访问（RAG 需认证）', async ({ page }) => {
    await page.goto('/knowledge');
    await expect(page).toHaveURL(/\/login/);
  });
});
