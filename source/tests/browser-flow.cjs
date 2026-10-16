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
  let questionWrites = 0;
  let unsupportedCalls = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && /\/records$/.test(request.url())) recordPosts += 1;
    if (request.method() === 'PATCH' && /\/api\/records\/\d+$/.test(request.url())) recordPatches += 1;
    else if (request.method() === 'DELETE' && /\/api\/records\/\d+$/.test(request.url())) recordDeletes += 1;
    else if (request.method() === 'PATCH' && /\/api\/vehicles\/\d+$/.test(request.url())) vehiclePatches += 1;
    else if (['PATCH', 'DELETE'].includes(request.method()) && /\/question-selections$/.test(request.url())) questionWrites += 1;
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
    const referenceVehicleButton = page.locator('[data-fill-reference-vehicle]');
    await referenceVehicleButton.waitFor({ state: 'visible' });
    await referenceVehicleButton.click();
    assert.equal(await page.locator('#manufacturer').inputValue(), '기아');
    assert.equal(await page.locator('#model').inputValue(), 'K5');
    assert.equal(await page.locator('#generation').inputValue(), 'DL3');
    assert.equal(await page.locator('#model-year').inputValue(), '2021');
    assert.equal(await page.locator('#engine').inputValue(), 'G2.0 CVVL');
    assert.equal(await page.locator('#fuel').inputValue(), '가솔린');
    assert.equal(await page.locator('#transmission').inputValue(), '자동');
    assert.equal(await page.locator('#mileage').inputValue(), '');
    assert.equal(await page.locator('#reference-date').inputValue(), '');
    assert.equal(await page.locator('#in-service-date').inputValue(), '');
    await page.locator('[data-reference-vehicle-status]').filter({ hasText: '실제 주행거리와 측정일' }).waitFor();
    check('new vehicle form fills only the reference K5 spec and leaves user-specific values empty');
    await page.locator('#manufacturer').fill('기아');
    await page.locator('#model').fill('K5');
    await page.locator('#generation').selectOption('DL3');
    await page.locator('#model-year').fill('2021');
    await page.locator('#engine').fill('G2.0 CVVL');
    await page.locator('#fuel').fill('가솔린');
    await page.locator('#transmission').fill('자동');
    await page.locator('#mileage').fill('90000');
    await page.locator('#in-service-date').fill('2021-10-15');
    await page.locator('#reference-date').fill(new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
    await page.locator('input[name=conditions][value=normal]').check();
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    await page.locator('[data-vehicle-name]').filter({ hasText: 'K5 DL3' }).waitFor();
    await page.locator('[data-demo-data-note]').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    await page.locator('[data-management-content] .badge').filter({ hasText: '사용 권리 확인 중' }).first().waitFor();
    check('vehicle stored and candidate guidance displays pending-rights status');
    await page.goto(`${base}/vehicle`);
    await page.locator('[data-save-status]').filter({ hasText: '정보 수정' }).waitFor();
    assert.equal(await page.locator('[data-fill-reference-vehicle]').isHidden(), true);
    check('existing vehicle hides the reference-spec shortcut');
    await page.goto(`${base}/dashboard`);

    await page.goto(`${base}/items/engine-oil`);
    const oilQuestionGroup = page.locator('[data-management-questions] [data-question-group^="engine-oil:"]').first();
    const oilQuestion = oilQuestionGroup.locator('[data-question-key]').first();
    await oilQuestion.waitFor();
    const oilQuestionKey = await oilQuestion.getAttribute('data-question-key');
    const saveOilQuestion = page.waitForResponse(response => response.url().endsWith('/question-selections') && response.request().method() === 'PATCH');
    await oilQuestion.check();
    assert.equal((await saveOilQuestion).status(), 200);
    await page.goto(`${base}/questions`);
    await page.locator('[data-question-clear]:enabled').waitFor();
    const savedOilQuestion = page.locator(`[data-question-key="${oilQuestionKey}"]`);
    await savedOilQuestion.waitFor();
    assert.equal(await savedOilQuestion.isChecked(), true);
    check('presentation engine-oil mechanic question is saved before recording work');
    const savedOilQuestionGroup = page.locator('[data-management-questions] [data-question-group^="engine-oil:"]').first();
    await savedOilQuestionGroup.getByRole('link', { name: '이 항목의 정비 결과 기록' }).click();
    await page.waitForURL('**/maintenance/new?*');
    assert.equal(await page.locator('#item').inputValue(), 'engine-oil');
    assert.equal(await page.locator('#work-type').inputValue(), 'unknown');
    const presentationDate = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    await page.locator('#work-type').selectOption('replacement');
    await page.locator('#work-date').fill(presentationDate);
    await page.locator('#work-mileage').fill('90000');
    await page.locator('#result').fill('시연용 가상 사례 · 엔진오일 교환');
    await page.locator('#record-form button[type=submit]').click();
    await page.waitForURL('**/timeline');
    await page.locator('[data-saved-records]').filter({ hasText: '시연용 가상 사례 · 엔진오일 교환' }).waitFor();
    check('presentation saves the explicitly labeled virtual engine-oil replacement');
    await page.goto(`${base}/dashboard`);
    const presentationOil = page.locator('[data-management-content] article').filter({ hasText: '엔진 오일·오일필터' });
    const expectedOilDate = new Date(`${presentationDate}T00:00:00Z`);
    expectedOilDate.setUTCFullYear(expectedOilDate.getUTCFullYear() + 1);
    await presentationOil.filter({
      hasText: `거리 기준: 105,000km · 기간 기준: ${expectedOilDate.toISOString().slice(0, 10)}`,
    }).waitFor();
    await presentationOil.locator('.badge').filter({ hasText: '확인된 관리 이력' }).waitFor();
    await presentationOil.locator('.badge').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    check('presentation recalculates 105,000km or 12 months with both history and pending-rights labels');
    await page.goto(`${base}/timeline`);
    const presentationOilEntry = page.locator('[data-saved-records] .saved-entry').filter({ hasText: '시연용 가상 사례 · 엔진오일 교환' });
    const deletePresentationOil = page.waitForResponse(response => response.url().startsWith(`${base}/api/records/`) && response.request().method() === 'DELETE');
    await presentationOilEntry.locator('.record-delete').click();
    await page.locator('.delete-confirmation').getByRole('button', { name: '삭제' }).click();
    assert.equal((await deletePresentationOil).status(), 200);
    await presentationOilEntry.waitFor({ state: 'detached' });
    check('presentation test removes only its own temporary replacement record');
    await page.goto(`${base}/questions`);
    const clearOilQuestion = page.waitForResponse(response => response.url().endsWith('/question-selections') && response.request().method() === 'DELETE');
    await page.locator('[data-question-clear]').click();
    assert.equal((await clearOilQuestion).status(), 200);
    await page.locator('[data-question-message]').filter({ hasText: '질문 선택을 초기화했습니다' }).waitFor();
    check('presentation test clears its temporary mechanic question selection');
    await page.goto(`${base}/dashboard`);

    let coolantRow = page.locator('[data-management-content] article').filter({ hasText: '냉각수' });
    await coolantRow.filter({ hasText: '거리 기준: 200,000km · 기간 기준: 2031-10-15' }).waitFor();
    await coolantRow.locator('.badge').filter({ hasText: '이력 미확인' }).waitFor();
    check('90,000km coolant guidance shows first 200,000km or 10-year milestone and unknown history');
    const airFilterInspection = page.locator('[data-management-content] article')
      .filter({ hasText: '엔진 에어클리너 필터 · 점검' });
    const airFilterReplacement = page.locator('[data-management-content] article')
      .filter({ hasText: '엔진 에어클리너 필터 · 교환' });
    await airFilterInspection.locator('.badge').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    await airFilterReplacement.locator('.badge').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    await airFilterInspection.filter({ hasText: '거리 기준: 10,000km' }).waitFor();
    await airFilterReplacement.filter({ hasText: '거리 기준: 40,000km' }).waitFor();
    check('engine air-cleaner inspection and replacement schedules are separate');

    const sparkPlugRow = page.locator('[data-management-content] article').filter({ hasText: '점화플러그' });
    await sparkPlugRow.filter({ hasText: '거리 기준: 165,000km' }).waitFor();
    await sparkPlugRow.locator('.badge').filter({ hasText: '이력 미확인' }).waitFor();
    await sparkPlugRow.locator('.badge').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    await page.goto(`${base}/items/spark-plugs`);
    const sparkPlugDetail = page.locator('[data-management-content]');
    await sparkPlugDetail.locator('article').filter({ hasText: '점화플러그' }).waitFor();
    await page.locator('[data-management-questions]').filter({ hasText: '점화플러그' }).waitFor();
    check('spark-plug detail uses the exact vehicle candidate and shows mechanic questions');

    await page.goto(`${base}/maintenance/new`);
    await page.locator('#item').selectOption('spark-plugs');
    await page.locator('#work-type').selectOption('replacement');
    await page.locator('#work-date').fill('2026-02-01');
    await page.locator('#work-mileage').fill('80000');
    await page.locator('#result').fill('브라우저 시험 점화플러그 교환');
    await page.locator('#record-form button[type=submit]').click();
    await page.waitForURL('**/timeline');
    await page.locator('[data-saved-records]').filter({ hasText: '브라우저 시험 점화플러그 교환' }).waitFor();
    await page.goto(`${base}/dashboard`);
    await page.locator('[data-management-content] article').filter({ hasText: '점화플러그' })
      .filter({ hasText: '거리 기준: 245,000km' }).waitFor();
    await page.locator('[data-management-content] article').filter({ hasText: '점화플러그' })
      .locator('.badge').filter({ hasText: '확인된 관리 이력' }).waitFor();
    check('spark-plug replacement record persists and restarts the 165,000km interval');

    await page.goto(`${base}/vehicle`);
    await page.locator('input[name=conditions][value=severe]').check();
    await page.locator('input[name=severe_condition_codes][value="2"]').check();
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    const severeAirFilter = page.locator('[data-management-content] article').filter({ hasText: '엔진 에어클리너 필터 · 점검' });
    await severeAirFilter.filter({ hasText: '가혹조건 2·5번' }).waitFor();
    assert.equal(await page.locator('[data-management-content] article').filter({ hasText: '점화플러그' }).count(), 0);
    check('severe dust-driving condition selects air-cleaner inspection without spark-plug guidance');

    await page.goto(`${base}/vehicle`);
    await page.locator('input[name=severe_condition_codes][value="2"]').waitFor();
    assert.equal(await page.locator('input[name=conditions][value=severe]').isChecked(), true);
    assert.equal(await page.locator('input[name=severe_condition_codes][value="2"]').isChecked(), true);
    await page.locator('input[name=severe_condition_codes][value="2"]').uncheck();
    await page.locator('input[name=severe_condition_codes][value="1"]').check();
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    const severeSparkPlugs = page.locator('[data-management-content] article').filter({ hasText: '점화플러그 · 점검' });
    await severeSparkPlugs.filter({ hasText: '가혹조건 1·3·7·9번' }).waitFor();
    assert.equal(await page.locator('[data-management-content] article').filter({ hasText: '엔진 에어클리너 필터' }).count(), 0);
    check('severe short-trip condition selects spark-plug inspection without air-cleaner guidance');

    await page.goto(`${base}/vehicle`);
    await page.locator('input[name=conditions][value=normal]').check();
    assert.equal(await page.locator('input[name=severe_condition_codes][value="1"]').isChecked(), false);
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');

    await page.goto(`${base}/vehicle`);
    await page.locator('[data-save-status]').filter({ hasText: '정보 수정' }).waitFor();
    assert.equal(await page.locator('#vehicle-form button[type=submit]').isVisible(), true);
    assert.equal(await page.locator('#model').inputValue(), 'K5');
    assert.equal(await page.locator('#model').isDisabled(), false);
    assert.equal(await page.locator('#mileage').isDisabled(), false);
    assert.equal(await page.locator('#reference-date').isDisabled(), false);
    const patchesBeforeVehicleUpdate = vehiclePatches;
    await page.locator('#model-year').fill('2022');
    await page.locator('#mileage').fill('91000');
    const today = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    await page.locator('#reference-date').fill(today);
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    assert.equal(vehiclePatches - patchesBeforeVehicleUpdate, 1);
    await page.goto(`${base}/vehicle`);
    await page.locator('[data-save-status]').filter({ hasText: '정보 수정' }).waitFor();
    assert.equal(await page.locator('#model-year').inputValue(), '2022');
    assert.equal(await page.locator('#mileage').inputValue(), '91000');
    assert.equal(await page.locator('#reference-date').inputValue(), today);
    check('vehicle details, mileage, and measurement date update and persist');
    await page.goto(`${base}/dashboard`);
    await page.locator('[data-demo-data-note]').filter({ hasText: '현재 차량 사양은 범위 밖이라 이 기준을 적용하지 않습니다' }).waitFor();
    check('out-of-scope model year is saved without applying the 2021 K5 criteria');
    await page.goto(`${base}/vehicle`);
    await page.locator('[data-save-status]').filter({ hasText: '정보 수정' }).waitFor();
    await page.locator('#model-year').fill('2021');
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    await page.locator('[data-demo-data-note]').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    await page.locator('[data-management-content] .badge').filter({ hasText: '사용 권리 확인 중' }).first().waitFor();
    check('returning to supported model year calculates candidate criteria with pending-rights status');

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
    const engineOilEntry = page.locator('[data-saved-records] .saved-entry').filter({ hasText: '브라우저 시험 엔진오일 교환' });
    await engineOilEntry.waitFor();
    assert.equal(recordPosts - before, 1);
    assert.equal(await page.locator('[data-saved-records] .saved-entry').count(), 2);
    assert.equal(await engineOilEntry.locator('.record-delete').count(), 1);
    assert.equal(await engineOilEntry.getByRole('button', { name: '기록 수정' }).count(), 1);
    await page.unroute('**/api/vehicles/*/records');
    check('double submit stores one record and live edit/delete controls appear');
    await page.reload();
    await page.locator('[data-saved-records]').filter({ hasText: '브라우저 시험' }).waitFor();
    check('timeline persists after reload');

    await page.goto(`${base}/dashboard`);
    await page.locator('[data-dashboard-records]').filter({ hasText: '입력한 기록 2건' }).waitFor();
    await page.locator('[data-management-content]').filter({ hasText: '확인된 관리 이력' }).waitFor();
    await page.locator('[data-logout]').click();
    await page.waitForURL('**/login');
    await login(username);
    await page.locator('[data-dashboard-records]').filter({ hasText: '입력한 기록 2건' }).waitFor();
    check('record persists after logout and relogin');
    await page.goto(`${base}/timeline`);
    await engineOilEntry.getByRole('button', { name: '기록 수정' }).click();
    await engineOilEntry.locator('.record-editor [name=result]').fill('수정된 브라우저 시험 기록');
    await engineOilEntry.locator('.record-editor button[type=submit]').click();
    const updatedEngineOilEntry = page.locator('[data-saved-records] .saved-entry').filter({ hasText: '수정된 브라우저 시험 기록' });
    await updatedEngineOilEntry.waitFor();
    assert.equal(recordPatches, 1);
    check('live record edit persists the corrected value');
    await page.goto(base + '/vehicle');
    await page.locator('input[name=conditions][value=severe]').check();
    await page.locator('input[name=severe_condition_codes][value="12"]').check();
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    const severeOilRow = page.locator('[data-management-content] article').filter({ hasText: '엔진 오일·오일필터' });
    await severeOilRow.filter({ hasText: '거리 기준: 27,500km · 기간 기준: 2026-07-31' }).waitFor();
    await severeOilRow.filter({ hasText: '적용한 가혹조건: 12번' }).waitFor();
    await severeOilRow.locator('.badge').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    check('severe engine-oil schedule uses and displays the selected condition code');
    await page.goto(`${base}/vehicle`);
    await page.locator('input[name=conditions][value=normal]').check();
    await page.locator('#vehicle-form button[type=submit]').click();
    await page.waitForURL('**/dashboard');
    await page.goto(`${base}/timeline`);
    await updatedEngineOilEntry.locator('.record-delete').click();
    await page.locator('.delete-confirmation').getByRole('button', { name: '삭제' }).click();
    await updatedEngineOilEntry.waitFor({ state: 'detached' });
    await page.locator('[data-saved-records] .saved-entry').filter({ hasText: '브라우저 시험 점화플러그 교환' }).waitFor();
    assert.equal(await page.locator('[data-saved-records] .saved-entry').count(), 1);
    assert.equal(recordDeletes, 2);
    check('live record deletion requires confirmation and removes the record');
    await page.goto(`${base}/items/engine-oil`);
    const detail = page.locator('[data-management-content]');
    await detail.filter({ hasText: '기준' }).waitFor();
    assert.equal(await detail.locator('article').count(), 1);
    assert.match(await detail.innerText(), /엔진 오일·오일필터/);
    assert.doesNotMatch(await detail.innerText(), /점화플러그/);
    await page.goto(`${base}/questions`);
    await page.locator('[data-management-questions] article h2').first().waitFor();
    assert.ok(await page.locator('[data-management-questions] article h2').count() > 1);
    check('detail and question pages use server management');

    const firstQuestion = page.locator('[data-management-questions] [data-question-key]').first();
    await page.locator('[data-question-clear]:enabled').waitFor();
    const selectedKey = await firstQuestion.getAttribute('data-question-key');
    const savedSelection = page.waitForResponse(response => response.url().endsWith('/question-selections') && response.request().method() === 'PATCH');
    await firstQuestion.check();
    assert.equal((await savedSelection).status(), 200);
    await page.locator('[data-question-message]').filter({ hasText: '질문 선택을 내 차량에 저장했습니다' }).waitFor();
    await page.reload();
    await page.locator('[data-question-clear]:enabled').waitFor();
    const savedQuestion = page.locator(`[data-question-key="${selectedKey}"]`);
    assert.equal(await savedQuestion.isChecked(), true);
    await page.screenshot({ path: path.join(screenshotDir, 'questions-live-390.png') });
    await page.setViewportSize({ width: 320, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1));
    await page.screenshot({ path: path.join(screenshotDir, 'questions-live-320.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    check('selected mechanic question persists after reload');

    await page.route('**/question-selections', async route => {
      if (route.request().method() === 'PATCH') await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: '시험용 저장 실패' } }) });
      else await route.continue();
    });
    await savedQuestion.uncheck();
    await page.locator('[data-question-message]').filter({ hasText: '서버의 현재 선택을 다시 불러왔습니다' }).waitFor();
    assert.equal(await savedQuestion.isChecked(), true);
    await page.unroute('**/question-selections');
    check('failed question save restores server state without reporting success');

    const ballJointQuestions = page.locator('[data-question-group^="ball-joint:front_right:"]');
    await ballJointQuestions.getByRole('link', { name: '이 항목의 정비 결과 기록 →' }).click();
    await page.waitForURL('**/maintenance/new?*');
    assert.equal(await page.locator('#item').inputValue(), 'ball-joint');
    assert.equal(await page.locator('#component-position').inputValue(), 'front_right');
    assert.equal(await page.locator('#work-type').inputValue(), 'unknown');
    assert.equal(await page.locator('#work-date').inputValue(), '');
    check('question links prefill only the component and position, not completed work');
    await page.goto(`${base}/maintenance/new?item=engine-oil&position=front_right`);
    assert.equal(await page.locator('#component-position').inputValue(), 'unknown');
    await page.goto(`${base}/maintenance/new?item=%3Cscript%3E&position=invalid`);
    assert.equal(await page.locator('#item').inputValue(), 'engine-oil');
    assert.equal(await page.locator('#component-position').inputValue(), 'unknown');
    assert.equal(await page.locator('#work-type').inputValue(), 'unknown');
    check('record prefill ignores invalid items and unrelated component positions');

    await page.goto(`${base}/dashboard`);
    await page.locator('[data-logout]').click();
    await page.waitForURL('**/login');
    await login(username);
    await page.goto(`${base}/questions`);
    await page.locator('[data-question-clear]:enabled').waitFor();
    assert.equal(await savedQuestion.isChecked(), true);
    await page.locator('[data-question-clear]').click();
    await page.locator('[data-question-message]').filter({ hasText: '질문 선택을 초기화했습니다' }).waitFor();
    assert.equal(await savedQuestion.isChecked(), false);
    assert.equal(questionWrites, 5);
    check('question selection survives relogin and can be cleared independently');

    await page.goto(`${base}/maintenance/new`);
    await page.locator('#item').selectOption('lower-arm');
    await page.locator('#component-position').selectOption('front_right');
    await page.locator('#work-type').selectOption('replacement');
    await page.locator('#work-date').fill('2026-02-01');
    await page.locator('#work-mileage').fill('21000');
    await page.locator('#result').fill('브라우저 시험 로워암 교환');
    await page.locator('#record-form button[type=submit]').click();
    await page.waitForURL('**/timeline');
    await page.locator('[data-saved-records]').filter({ hasText: '로워암 교환' }).waitFor();
    await page.goto(`${base}/dashboard`);
    const ballJointRow = page.locator('[data-management-content] article')
      .filter({ hasText: '볼 조인트 · 앞 오른쪽' });
    await ballJointRow.waitFor();
    await ballJointRow.locator('.badge').filter({ hasText: '이력 미확인' }).waitFor();
    check('lower-arm replacement persists separately and leaves ball-joint history unknown');

    for (const [itemKey, mileage] of [['brake-fluid', '20000'], ['cabin-air-filter', '21000']]) {
      await page.goto(`${base}/maintenance/new`);
      await page.locator('#item').selectOption(itemKey);
      await page.locator('#work-type').selectOption('replacement');
      await page.locator('#work-date').fill('2026-03-01');
      await page.locator('#work-mileage').fill(mileage);
      await page.locator('#result').fill(`브라우저 시험 ${itemKey} 교환`);
      await page.locator('#record-form button[type=submit]').click();
      await page.waitForURL('**/timeline');
      await page.locator('[data-saved-records]').filter({ hasText: `브라우저 시험 ${itemKey} 교환` }).waitFor();
    }
    await page.goto(`${base}/dashboard`);
    for (const [itemKey, nextMileage] of [['brake-fluid', '70,000'], ['cabin-air-filter', '36,000']]) {
      const row = page.locator('[data-management-content] article').filter({ hasText: itemKey === 'brake-fluid' ? '브레이크액' : '공조장치용 에어필터' });
      await row.locator('.badge').filter({ hasText: '확인된 관리 이력' }).waitFor();
      assert.match(await row.innerText(), new RegExp(nextMileage));
      await row.locator('.badge').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    }
    check('brake fluid and cabin filter records save and update candidate next-mileage guidance');

    for (const [workType, workDate, mileage] of [
      ['replacement', '2026-02-01', '80000'], ['inspection', '2026-03-01', '90000'],
    ]) {
      await page.goto(`${base}/maintenance/new`);
      await page.locator('#item').selectOption('air-filter');
      await page.locator('#work-type').selectOption(workType);
      await page.locator('#work-date').fill(workDate);
      await page.locator('#work-mileage').fill(mileage);
      await page.locator('#result').fill(`브라우저 시험 엔진 에어클리너 ${workType}`);
      await page.locator('#record-form button[type=submit]').click();
      await page.waitForURL('**/timeline');
    }
    await page.goto(`${base}/dashboard`);
    const airFilterInspectionAfterSave = page.locator('[data-management-content] article')
      .filter({ hasText: '엔진 에어클리너 필터 · 점검' });
    const airFilterReplacementAfterSave = page.locator('[data-management-content] article')
      .filter({ hasText: '엔진 에어클리너 필터 · 교환' });
    await airFilterInspectionAfterSave.filter({ hasText: '거리 기준: 100,000km' }).waitFor();
    await airFilterReplacementAfterSave.filter({ hasText: '거리 기준: 120,000km' }).waitFor();
    await airFilterInspectionAfterSave.locator('.badge').filter({ hasText: '확인된 관리 이력' }).waitFor();
    check('air-cleaner inspection and replacement histories save and restart their own schedules');

    await page.goto(`${base}/maintenance/new`);
    await page.locator('#item').selectOption('coolant');
    await page.locator('#work-type').selectOption('replacement');
    await page.locator('#work-date').fill('2025-10-15');
    await page.locator('#work-mileage').fill('80000');
    await page.locator('#result').fill('브라우저 시험 냉각수 교환');
    await page.locator('#record-form button[type=submit]').click();
    await page.waitForURL('**/timeline');
    await page.locator('[data-saved-records]').filter({ hasText: '브라우저 시험 냉각수 교환' }).waitFor();
    await page.goto(`${base}/dashboard`);
    coolantRow = page.locator('[data-management-content] article').filter({ hasText: '냉각수' });
    await coolantRow.filter({ hasText: '거리 기준: 120,000km · 기간 기준: 2027-10-15' }).waitFor();
    await coolantRow.locator('.badge').filter({ hasText: '확인된 관리 이력' }).waitFor();
    await coolantRow.locator('.badge').filter({ hasText: '사용 권리 확인 중' }).waitFor();
    check('coolant replacement persists and restarts both 40,000km and 24-month intervals');

    await register(`${username}_b`);
    await login(`${username}_b`);
    await page.locator('[data-vehicle-name]').filter({ hasText: '등록' }).waitFor();
    assert.equal(await page.locator('[data-dashboard-records]').innerText(), '저장된 관리기록이 없습니다.');
    assert.equal(await page.locator('[data-vehicle-name]').innerText(), '차량을 먼저 등록해 주세요');
    assert.equal(await page.locator('[data-management-controls]').isVisible(), false);
    await page.locator('[data-management-content]').getByRole('link', { name: '차량 등록하기' }).waitFor();
    check('second account does not see first account data');
    await login(username);
    await page.locator('[data-management-content] article').first().waitFor();
    await page.goto(`${base}/vehicle`);
    const originalVehicleId = await page.locator('[data-vehicle-select]').inputValue();
    for (const model of ['시연 차량 2', '시연 차량 3']) {
      await page.goto(`${base}/vehicle`);
      await page.locator('[data-add-vehicle]').click();
      await page.waitForURL('**/vehicle?new=1');
      await page.locator('#manufacturer').fill('기아');
      await page.locator('#model').fill(model);
      await page.locator('#vehicle-form button[type=submit]').click();
      await page.waitForURL('**/dashboard');
      await page.locator('[data-vehicle-name]').filter({ hasText: model }).waitFor();
    }
    await page.goto(`${base}/vehicle`);
    assert.equal(await page.locator('[data-vehicle-select] option').count(), 3);
    assert.equal(await page.locator('[data-add-vehicle]').isHidden(), true);
    const fourthVehicleStatus = await page.evaluate(async () => {
      try {
        await window.ChageunApi.vehicles.create({ manufacturer: '기아', model: '시연 차량 4' });
        return 201;
      } catch (error) {
        return error.status;
      }
    });
    assert.equal(fourthVehicleStatus, 409);
    const storedVehicles = await page.evaluate(async () => (await window.ChageunApi.vehicles.list()).data);
    assert.equal(storedVehicles.length, 3);
    check('account can register three vehicles and the live API rejects a fourth without storing it');

    const thirdVehicleId = await page.locator('[data-vehicle-select]').inputValue();
    await Promise.all([
      page.waitForNavigation(),
      page.locator('[data-vehicle-select]').selectOption(originalVehicleId),
    ]);
    assert.equal(await page.locator('#model').inputValue(), 'K5');
    await page.goto(`${base}/dashboard`);
    await page.locator('[data-vehicle-name]').filter({ hasText: 'K5 DL3' }).waitFor();
    await page.locator('[data-dashboard-records]').filter({ hasText: '입력한 기록' }).waitFor();
    assert.match(await page.locator('[data-dashboard-records]').innerText(), /입력한 기록/);
    await Promise.all([
      page.waitForNavigation(),
      page.locator('[data-active-vehicle-select]').selectOption(thirdVehicleId),
    ]);
    await page.locator('[data-vehicle-name]').filter({ hasText: '시연 차량 3' }).waitFor();
    await page.locator('[data-dashboard-records]').filter({ hasText: '저장된 관리기록이 없습니다.' }).waitFor();
    assert.equal(await page.locator('[data-dashboard-records]').innerText(), '저장된 관리기록이 없습니다.');
    check('active vehicle selection switches the dashboard and keeps each vehicle history separate');

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
