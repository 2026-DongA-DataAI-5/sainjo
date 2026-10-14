// 전용 시험 계정으로 UI에서 실제 서버 저장·재로그인·계정 분리를 확인합니다.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const base = process.env.CHAGEUN_BROWSER_BASE || 'http://127.0.0.1:8081';
const password = 'browser-test-only-password';
const username = `ui_${Date.now()}`;
const screenshotDir = path.resolve(__dirname, '../../.mysql-test/screenshots');
fs.mkdirSync(screenshotDir, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.CHAGEUN_BROWSER_EXECUTABLE ? { executablePath: process.env.CHAGEUN_BROWSER_EXECUTABLE } : {}) });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let recordPosts = 0;
  let recordPatches = 0;
  let recordDeletes = 0;
  let vehiclePatches = 0;
  let unsupportedCalls = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && /\/records$/.test(request.url())) recordPosts += 1;
    if (request.method() === 'PATCH' && /\/api\/records\/\d+$/.test(request.url())) recordPatches += 1;
    else if (request.method() === 'DELETE' && /\/api\/records\/\d+$/.test(request.url())) recordDeletes += 1;
    else if (request.method() === 'PATCH' && /\/api\/vehicles\/\d+$/.test(request.url())) vehiclePatches += 1;
    else if (['PATCH', 'DELETE'].includes(request.method())) unsupportedCalls += 1;
  });
  const checks = [];
  const check = name => { checks.push(name); console.log('PASS', name); };
  async function login(name) {
    await page.goto(`${base}/login`);
    await page.locator('#username').fill(name);
    await page.locator('#password').fill(password);
    await page.locator('#auth-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    await page.locator('[data-account-username]').filter({ hasText: name }).waitFor();
  }
  async function register(name) {
    await page.goto(`${base}/register`);
    await page.locator('#username').fill(name);
    await page.locator('#password').fill(password);
    await page.locator('#auth-form button[type=submit]').click();
    await page.locator('#auth-form > .form-message').filter({ hasText: '가입이 완료되었습니다' }).waitFor();
  }
  try {
    await page.goto(`${base}/vehicle`);
    await page.waitForURL('**/login?required=1');
    check('anonymous vehicle page redirects to login');
    await register(username);
    await login(username);
    await page.locator('[data-vehicle-name]').filter({ hasText: '등록' }).waitFor();
    check('register and login show account and empty vehicle');

    await page.goto(`${base}/vehicle`);
    await page.locator('#vehicle-form button[type=submit]').waitFor({ state: 'visible' });
    await page.locator('#manufacturer').fill('기아');
    await page.locator('#model').fill('K5');
    await page.locator('#generation').selectOption('DL3');
    await page.locator('#model-year').fill('2021');
    await page.locator('#engine').fill('G2.0 CVVL');
    await page.locator('#fuel').fill('가솔린');
    await page.locator('#transmission').fill('자동');
    await page.locator('#mileage').fill('25000');
    await page.locator('#reference-date').fill(new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
    await page.locator('input[name=conditions][value=normal]').check();
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    await page.locator('[data-vehicle-name]').filter({ hasText: 'K5 DL3' }).waitFor();
    await page.locator('[data-management-content]').filter({ hasText: '기준' }).waitFor();
    check('vehicle stored and server management unavailable state shown');
    await page.goto(`${base}/vehicle`);
    await page.locator('[data-save-status]').filter({ hasText: '수정' }).waitFor();
    assert.equal(await page.locator('#vehicle-form button[type=submit]').isVisible(), true);
    assert.equal(await page.locator('#model').inputValue(), 'K5');
    assert.equal(await page.locator('#model').isDisabled(), true);
    assert.equal(await page.locator('#mileage').isDisabled(), false);
    assert.equal(await page.locator('#reference-date').isDisabled(), false);
    await page.locator('#mileage').fill('26000');
    const today = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    await page.locator('#reference-date').fill(today);
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    assert.equal(vehiclePatches, 1);
    await page.goto(`${base}/vehicle`);
    assert.equal(await page.locator('#mileage').inputValue(), '26000');
    assert.equal(await page.locator('#reference-date').inputValue(), today);
    check('vehicle basics stay read only while mileage and measurement date update');

    await page.goto(`${base}/maintenance/new`);
    await page.locator('#work-type').selectOption('replacement');
    await page.locator('#work-date').fill('2026-01-31');
    await page.locator('#work-mileage').fill('20000');
    await page.locator('#result').fill('브라우저 시험 엔진오일 교환');
    await page.route('**/api/vehicles/*/records', async route => {
      if (route.request().method() === 'POST') {
        await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({
          error: { code: 'INTERNAL_ERROR', message: '시험용 저장 실패', fields: {} }, meta: { contract_version: '1.0' } }) });
      } else await route.continue();
    });
    await page.locator('#record-form button[type=submit]').click();
    await page.locator('#record-form .form-message').filter({ hasText: '실패' }).waitFor();
    assert.equal(await page.locator('#result').inputValue(), '브라우저 시험 엔진오일 교환');
    assert.equal(await page.locator('#work-mileage').inputValue(), '20000');
    await page.unroute('**/api/vehicles/*/records');
    check('save failure retains entered values');
    const before = recordPosts;
    await page.route('**/api/vehicles/*/records', async route => {
      if (route.request().method() === 'POST') await new Promise(resolve => setTimeout(resolve, 350));
      await route.continue();
    });
    await page.locator('#record-form button[type=submit]').dblclick();
    await page.waitForURL('**/timeline');
    await page.locator('[data-saved-records] .saved-entry').waitFor();
    assert.equal(recordPosts - before, 1);
    assert.equal(await page.locator('[data-saved-records] .saved-entry').count(), 1);
    assert.equal(await page.locator('.record-delete').count(), 1);
    assert.equal(await page.locator('.record-actions').getByRole('button', { name: '기록 수정' }).count(), 1);
    await page.unroute('**/api/vehicles/*/records');
    check('double submit stores one record and live edit/delete controls appear');
    await page.reload();
    await page.locator('[data-saved-records]').filter({ hasText: '브라우저 시험' }).waitFor();
    check('timeline persists after reload');

    await page.goto(`${base}/dashboard`);
    await page.locator('[data-dashboard-records]').filter({ hasText: '입력한 기록 1건' }).waitFor();
    await page.locator('[data-management-content]').filter({ hasText: '확인된 관리 이력' }).waitFor();
    await page.locator('[data-logout]').click();
    await page.waitForURL('**/login');
    await login(username);
    await page.locator('[data-dashboard-records]').filter({ hasText: '입력한 기록 1건' }).waitFor();
    check('record persists after logout and relogin');
    await page.goto(`${base}/timeline`);
    await page.locator('.record-actions').getByRole('button', { name: '기록 수정' }).click();
    await page.locator('.record-editor [name=result]').fill('수정된 브라우저 시험 기록');
    await page.locator('.record-editor button[type=submit]').click();
    await page.locator('[data-saved-records]').filter({ hasText: '수정된 브라우저 시험 기록' }).waitFor();
    assert.equal(recordPatches, 1);
    check('live record edit persists the corrected value');
    await page.locator('.record-actions .record-delete').click();
    await page.locator('.delete-confirmation').getByRole('button', { name: '삭제' }).click();
    await page.locator('[data-saved-records]').filter({ hasText: '아직 저장한 기록이 없습니다' }).waitFor();
    assert.equal(recordDeletes, 1);
    check('live record deletion requires confirmation and removes the record');
    await page.goto(`${base}/items/engine-oil`);
    await page.locator('[data-management-content]').filter({ hasText: '기준' }).waitFor();
    await page.goto(`${base}/questions`);
    await page.locator('[data-management-questions] p').first().waitFor();
    check('detail and question pages use server management');

    await register(`${username}_b`);
    await login(`${username}_b`);
    await page.locator('[data-vehicle-name]').filter({ hasText: '등록' }).waitFor();
    assert.equal(await page.locator('[data-dashboard-records]').innerText(), '저장된 관리기록이 없습니다.');
    assert.equal(await page.locator('[data-vehicle-name]').innerText(), '차량을 먼저 등록해 주세요');
    check('second account does not see first account data');
    await login(username);
    await page.locator('[data-management-content] article').waitFor();
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      assert.equal(overflow, false, `horizontal overflow at ${width}`);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(screenshotDir, 'dashboard-live-390.png'), fullPage: true });
    check('responsive widths 320 390 768 1440');
    assert.equal(unsupportedCalls, 0);
    assert.deepEqual(errors, []);
    check('no page script errors or unsupported requests');
    fs.writeFileSync(path.join(screenshotDir, 'browser-result.json'), JSON.stringify({ checks, count: checks.length }, null, 2));
    console.log('Browser checks:', checks.length);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
