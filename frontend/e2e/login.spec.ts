import { test, expect } from '@playwright/test';

test.describe('登录页', () => {
  test('应展示登录表单', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input')).toHaveCount(2);
    await expect(page.getByRole('button')).toBeVisible();
  });

  test('未登录访问首页应重定向登录', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });
});
