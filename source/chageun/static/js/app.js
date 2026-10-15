// 차량·관리 기록 화면을 API 클라이언트(ChageunApi)에 연결합니다.
// mock 미리보기와 live 서버 자료를 명시적으로 구분합니다.
// 판단 로직(교환 시기 계산)은 여기에 두지 않습니다. 서버 응답을 그대로 표시합니다.
(function () {
  'use strict';

  const api = window.ChageunApi;
  const QUESTION_STORAGE_KEY = 'chageun.questions.v1';
  const APP_BASE_PATH = document.documentElement.dataset.basePath || '';
  window.addEventListener('pageshow', (event) => {
    if (event.persisted && api.mode === 'live') window.location.reload();
  });

  const FIELD_LABELS = {
    manufacturer: '제조사',
    model: '모델',
    generation: '세대',
    year: '연식',
    engine: '엔진',
    fuel: '연료',
    transmission: '변속기',
    mileage: '주행거리',
    reference_date: '주행거리 측정 기준일',
    in_service_date: '최초 등록일',
    conditions: '운행조건',
    kind: '기록 종류',
    item_key: '관리항목',
    component_position: '정비 위치',
    item: '관리항목',
    work_type: '작업 유형',
    date: '정비·점검일',
    result: '기록 내용',
    source: '출처',
    checked_date: '자료 확인일',
    rights_status: '기준 이용 상태',
    review_status: '기준 검토 상태',
  };
  const WORK_TYPE_LABELS = { inspection: '점검', replacement: '교환', unknown: '작업 유형 미확인' };
  const KIND_LABELS = { previous_history: '이전 이력 입력', maintenance_result: '정비 결과 입력' };
  const ITEM_LABELS = { 'engine-oil': '엔진 오일·오일필터', 'air-filter': '엔진 에어클리너 필터', 'cabin-air-filter': '공조장치용 에어필터', 'brake-fluid': '브레이크액', coolant: '냉각수', 'spark-plugs': '점화플러그', 'drive-belt': '구동벨트', 'brake-pads-discs': '브레이크 패드·디스크', 'ball-joint': '볼 조인트', 'lower-arm': '로워암(컨트롤 암)', 'lower-arm-ball-joint': '로워암·볼 조인트 (과거 통합 기록)' };
  const POSITION_LABELS = { unknown: '위치 미확인', front: '앞쪽', rear: '뒤쪽', left: '왼쪽', right: '오른쪽', front_left: '앞 왼쪽', front_right: '앞 오른쪽', rear_left: '뒤 왼쪽', rear_right: '뒤 오른쪽' };
  const ACTION_LABELS = { inspection: '점검', replacement: '교환' };

  function appPath(path) {
    return `${APP_BASE_PATH}${path.startsWith('/') ? path : `/${path}`}`;
  }

  function appendText(parent, tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = text;
    parent.append(element);
    return element;
  }

  // 0km는 "0km"로, 값이 없을 때만 미확인으로 표시합니다.
  function formatMileage(value) {
    return value === null || value === undefined ? '주행거리 미확인' : `${Number(value).toLocaleString('ko-KR')}km`;
  }

  function numberText(value) {
    return value === null || value === undefined ? '미확인' : Number(value).toLocaleString('ko-KR');
  }

  function textOrUnknown(value) {
    return typeof value === 'string' && value.trim() ? value.trim() : '미확인';
  }

  function showMessage(element, text) {
    if (element) element.textContent = text;
  }

  // 오류 문구. 응답을 받지 못한 저장은 반영 여부를 알 수 없으므로 따로 안내합니다.
  function errorText(error) {
    if (error && error.uncertain) {
      return '저장 여부 확인 필요. 목록을 다시 불러와 기록이 있는지 확인해 주세요.';
    }
    const base = (error && error.message) || '저장하지 못했습니다. 입력 내용을 확인해 주세요.';
    const details = error && error.fields ? Object.entries(error.fields) : [];
    const detail = details.map(([name, text]) => `${FIELD_LABELS[name] || name}: ${text}`).join(' · ');
    return detail ? `${base} ${detail}` : base;
  }

  // 저장 중에는 버튼 글자를 바꾸지 않고 잠급니다(글자가 바뀌면 버튼 폭이 달라져 옆 링크가 밀려 올라옵니다).
  // 같은 화면의 링크도 저장이 끝날 때까지 누를 수 없게 막습니다.
  function lockForm(form, locked) {
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = locked;
    form.querySelectorAll('.form-actions a').forEach((link) => {
      link.style.pointerEvents = locked ? 'none' : '';
      link.setAttribute('aria-disabled', String(locked));
    });
    form.setAttribute('aria-busy', String(locked));
  }

  // 한 번에 한 요청만 보냅니다. 실패하면 입력은 그대로 남깁니다.
  function guardedSubmit(form, handler) {
    let busy = false;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (busy) return;
      busy = true;
      const message = form.querySelector('.form-message');
      lockForm(form, true);
      showMessage(message, '저장 중입니다. 잠시만 기다려 주세요.');
      try {
        await handler();
      } catch (error) {
        if (api.mode === 'live' && error.status === 401) redirectToLogin();
        showMessage(message, errorText(error));
      } finally {
        busy = false;
        lockForm(form, false);
      }
    });
  }

  async function loadVehicle() {
    const body = await api.vehicles.list();
    return body.data[0] || null;
  }

  async function loadRecords(vehicleId) {
    const records = [];
    let page = 1;
    while (true) {
      const body = await api.records.list(vehicleId, { page, pageSize: 100 });
      records.push(...body.data);
      if (body.data.length < 100 || records.length >= body.meta.pagination.total) return records;
      page += 1;
    }
  }

  function readSelectedQuestions() {
    try {
      const value = JSON.parse(localStorage.getItem(QUESTION_STORAGE_KEY) || '[]');
      return Array.isArray(value) ? value.filter((key) => typeof key === 'string') : [];
    } catch {
      return [];
    }
  }

  // ───────────────────────── 차량 정보 ─────────────────────────
  function vehicleFromForm(form) {
    const value = (name) => form.elements.namedItem(name).value;
    const generation = value('generation');
    return {
      manufacturer: api.convert.text(value('manufacturer')),
      model: api.convert.text(value('model')),
      generation: generation === 'unknown' ? null : generation,
      year: api.convert.int(value('year')),
      engine: api.convert.text(value('engine')),
      fuel: api.convert.text(value('fuel')),
      transmission: api.convert.text(value('transmission')),
      mileage: api.convert.int(value('mileage')),
      reference_date: api.convert.date(value('reference_date')),
      in_service_date: api.convert.date(value('in_service_date')),
      conditions: form.querySelector('input[name="conditions"]:checked')?.value || 'unknown',
      severe_condition_codes: form.querySelector('input[name="conditions"]:checked')?.value === 'severe'
        ? [...form.querySelectorAll('input[name="severe_condition_codes"]:checked')].map((field) => Number(field.value))
        : [],
    };
  }

  function fillVehicleForm(form, vehicle) {
    for (const name of ['manufacturer', 'model', 'generation', 'year', 'engine', 'fuel', 'transmission', 'mileage', 'reference_date', 'in_service_date']) {
      const field = form.elements.namedItem(name);
      const raw = vehicle[name];
      if (name === 'generation') field.value = raw || 'unknown';
      else field.value = raw === null || raw === undefined ? '' : String(raw);
    }
    const condition = form.querySelector(`input[name="conditions"][value="${vehicle.conditions}"]`);
    if (condition) condition.checked = true;
    const severeCodes = Array.isArray(vehicle.severe_condition_codes) ? vehicle.severe_condition_codes.map(String) : [];
    form.querySelectorAll('input[name="severe_condition_codes"]').forEach((field) => {
      field.checked = severeCodes.includes(field.value);
    });
  }

  function syncSevereConditionControls(form) {
    const selected = form.querySelector('input[name="conditions"]:checked')?.value;
    const details = form.querySelector('[data-severe-conditions]');
    if (!details) return;
    details.hidden = selected !== 'severe';
    if (selected !== 'severe') {
      details.querySelectorAll('input[name="severe_condition_codes"]').forEach((field) => {
        field.checked = false;
      });
    }
  }

  async function initVehicleForm(form) {
    const status = form.querySelector('.form-message');
    form.querySelectorAll('input[name="conditions"]').forEach((field) => {
      field.addEventListener('change', () => syncSevereConditionControls(form));
    });
    syncSevereConditionControls(form);
    lockForm(form, true);
    showMessage(status, '차량 정보를 불러오는 중입니다.');
    try {
      const vehicle = await loadVehicle();
      if (vehicle) fillVehicleForm(form, vehicle);
      syncSevereConditionControls(form);
      if (vehicle && api.mode === 'live') {
        form.dataset.existingVehicle = 'true';
        form.querySelectorAll('input, select').forEach((field) => {
          field.disabled = false;
        });
        form.querySelector('button[type="submit"]').textContent = '차량 정보 수정 저장';
        form.querySelector('[data-save-status]').textContent = '등록 차량 · 정보 수정';
        showMessage(status, '수정할 항목만 바꾸세요. 제조사와 모델은 필수이며, 모르는 선택 항목은 비워 둘 수 있습니다.');
      } else {
        showMessage(status, '');
      }
    } catch (error) {
      form.dataset.loadFailed = 'true';
      if (api.mode === 'live' && error.status === 401) redirectToLogin();
      showMessage(status, errorText(error));
    } finally {
      lockForm(form, false);
      if (form.dataset.loadFailed) form.querySelector('button[type="submit"]').disabled = true;
    }
  }

  // ───────────────────────── 관리 기록 ─────────────────────────
  function recordFromForm(form) {
    const value = (name) => form.elements.namedItem(name).value;
    return {
      kind: form.dataset.recordKind,
      item_key: value('item'),
      component_position: value('component_position'),
      work_type: value('work_type'),
      date: api.convert.date(value('date')),
      mileage: api.convert.int(value('mileage')),
      result: api.convert.text(value('result')),
      source: api.convert.text(value('source')),
      checked_date: api.convert.date(value('checked_date')),
    };
  }

  function recordCard(record, status, onChanged) {
    const entry = document.createElement('article');
    entry.className = 'timeline-entry saved-entry';
    const date = appendText(entry, 'div', 'timeline-date', record.date || '날짜 미확인');
    appendText(date, 'span', '', formatMileage(record.mileage));

    const details = document.createElement('div');
    appendText(details, 'span', 'badge', KIND_LABELS[record.kind] || '기록');
    appendText(details, 'span', 'badge', WORK_TYPE_LABELS[record.work_type] || '작업 유형 미확인');
    const title = document.createElement('h3');
    title.textContent = ITEM_LABELS[record.item_key] || '관리항목 미확인';
    details.append(title);
    if (record.component_position && record.component_position !== 'unknown') {
      appendText(details, 'span', 'badge', POSITION_LABELS[record.component_position] || '위치 미확인');
    }
    appendText(details, 'p', '', record.result || '추가 메모 없음');
    const savedDate = new Date(record.created_at);
    const savedAt = typeof record.created_at === 'string' && !Number.isNaN(savedDate.getTime())
      ? savedDate.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false }) : '미확인';
    appendText(details, 'small', 'muted', `출처: ${textOrUnknown(record.source)} · 자료 확인일: ${record.checked_date || '미확인'} · 등록(한국 시간): ${savedAt}`);
    appendText(details, 'small', 'record-limit-note', '사용자 입력 · 외부 자료와 자동 대조되지 않음');

    const actions = document.createElement('div');
    actions.className = 'record-actions';
    const editButton = appendText(actions, 'button', 'button secondary', '기록 수정');
    editButton.type = 'button';
    const removeButton = appendText(actions, 'button', 'button secondary record-delete', '이 기록 삭제');
    removeButton.type = 'button';
    details.append(actions);

    const editor = document.createElement('form');
    editor.className = 'record-editor form-panel';
    editor.hidden = true;
    editor.setAttribute('aria-label', '관리 기록 수정');
    const editorGrid = document.createElement('div');
    editorGrid.className = 'form-grid';
    const addEditorField = (name, labelText, type, value, options = null) => {
      const wrapper = document.createElement('div');
      if (name === 'result') wrapper.className = 'full';
      const label = document.createElement('label');
      const id = `record-${record.id}-${name}`;
      label.htmlFor = id;
      label.textContent = labelText;
      let field;
      if (type === 'select') {
        field = document.createElement('select');
        for (const [optionValue, optionText] of options) {
          const option = document.createElement('option');
          option.value = optionValue;
          option.textContent = optionText;
          field.append(option);
        }
      } else if (type === 'textarea') {
        field = document.createElement('textarea');
        field.rows = 3;
      } else {
        field = document.createElement('input');
        field.type = type;
      }
      field.id = id;
      field.name = name;
      if (type === 'date') field.max = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Seoul' });
      if (name === 'mileage') {
        field.min = '0';
        field.max = '1000000';
        field.step = '1';
      }
      if (name === 'result') field.maxLength = 2000;
      if (name === 'source') field.maxLength = 100;
      field.value = value === null || value === undefined ? '' : String(value);
      wrapper.append(label, field);
      editorGrid.append(wrapper);
      return field;
    };
    const workTypeField = addEditorField('work_type', '작업 유형', 'select', record.work_type, [
      ['unknown', '작업 유형 미확인'], ['inspection', '점검'], ['replacement', '교환'],
    ]);
    const positionField = addEditorField('component_position', '정비 위치', 'select', record.component_position || 'unknown', [
      ['unknown', '위치 미확인·해당 없음'], ['front', '앞쪽'], ['rear', '뒤쪽'], ['left', '왼쪽'], ['right', '오른쪽'],
      ['front_left', '앞 왼쪽'], ['front_right', '앞 오른쪽'], ['rear_left', '뒤 왼쪽'], ['rear_right', '뒤 오른쪽'],
    ]);
    const dateField = addEditorField('date', '정비·점검일', 'date', record.date);
    const mileageField = addEditorField('mileage', '당시 주행거리 km', 'number', record.mileage);
    const resultField = addEditorField('result', '기록 내용', 'textarea', record.result);
    const sourceField = addEditorField('source', '이력 출처', 'text', record.source);
    const checkedDateField = addEditorField('checked_date', '자료 확인일', 'date', record.checked_date);
    const editorMessage = appendText(editor, 'p', 'form-message', '');
    editorMessage.setAttribute('role', 'status');
    editorMessage.setAttribute('aria-live', 'polite');
    const editorActions = document.createElement('div');
    editorActions.className = 'form-actions';
    const saveButton = appendText(editorActions, 'button', 'button primary', '수정 저장');
    saveButton.type = 'submit';
    const cancelEdit = appendText(editorActions, 'button', 'button secondary', '취소');
    cancelEdit.type = 'button';
    editor.append(editorGrid, editorActions);
    details.append(editor);

    editButton.addEventListener('click', () => {
      editor.hidden = false;
      editButton.hidden = true;
      workTypeField.focus();
    });
    cancelEdit.addEventListener('click', () => {
      editor.hidden = true;
      editButton.hidden = false;
      showMessage(editorMessage, '');
      editButton.focus();
    });
    editor.addEventListener('submit', async (event) => {
      event.preventDefault();
      saveButton.disabled = true;
      cancelEdit.disabled = true;
      showMessage(editorMessage, '수정 내용을 저장하고 있습니다.');
      try {
        await api.records.update(record.id, {
          work_type: workTypeField.value,
          component_position: positionField.value,
          date: api.convert.date(dateField.value),
          mileage: api.convert.int(mileageField.value),
          result: api.convert.text(resultField.value),
          source: api.convert.text(sourceField.value),
          checked_date: api.convert.date(checkedDateField.value),
        });
        onChanged();
      } catch (error) {
        if (api.mode === 'live' && error.status === 401) redirectToLogin();
        showMessage(editorMessage, errorText(error));
        if (error && error.uncertain) onChanged();
      } finally {
        saveButton.disabled = false;
        cancelEdit.disabled = false;
      }
    });

    const confirmation = document.createElement('div');
    confirmation.className = 'delete-confirmation';
    confirmation.setAttribute('role', 'group');
    confirmation.setAttribute('aria-label', '기록 삭제 확인');
    confirmation.hidden = true;
    appendText(confirmation, 'span', '', '이 기록을 삭제할까요? 삭제한 기록은 복구할 수 없습니다.');
    const cancelButton = appendText(confirmation, 'button', 'button secondary', '취소');
    cancelButton.type = 'button';
    const confirmButton = appendText(confirmation, 'button', 'button danger', '삭제');
    confirmButton.type = 'button';
    details.append(confirmation);

    removeButton.addEventListener('click', () => {
      confirmation.hidden = false;
      confirmButton.focus();
    });
    cancelButton.addEventListener('click', () => {
      confirmation.hidden = true;
      removeButton.focus();
    });
    confirmButton.addEventListener('click', async () => {
      confirmButton.disabled = true;
      cancelButton.disabled = true;
      try {
        await api.records.remove(record.id);
        onChanged();
      } catch (error) {
        if (api.mode === 'live' && error.status === 401) redirectToLogin();
        // 삭제 실패 시 항목은 그대로 둡니다. 응답을 못 받았다면 목록을 다시 불러옵니다.
        showMessage(status, errorText(error));
        confirmButton.disabled = false;
        cancelButton.disabled = false;
        if (error && error.uncertain) onChanged();
      }
    });

    entry.append(details);
    return entry;
  }

  async function renderTimeline(list, status) {
    list.replaceChildren();
    appendText(list, 'p', 'muted', '기록을 불러오는 중입니다.');
    try {
      const vehicle = await loadVehicle();
      list.replaceChildren();
      if (!vehicle) {
        appendText(list, 'p', 'muted', '차량 정보를 먼저 저장하면 기록이 여기에 표시됩니다.');
        return;
      }
      const records = await loadRecords(vehicle.id);
      if (records.length === 0) {
        appendText(list, 'p', 'muted', '아직 저장한 기록이 없습니다. 기록 없음은 미정비를 뜻하지 않습니다.');
        return;
      }
      for (const record of records) {
        list.append(recordCard(record, status, () => renderTimeline(list, status)));
      }
    } catch (error) {
      list.replaceChildren();
      if (api.mode === 'live' && error.status === 401) redirectToLogin();
      appendText(list, 'p', 'muted', errorText(error));
    }
  }

  function bindExport(button) {
    button.addEventListener('click', async () => {
      const status = document.querySelector('[data-export-message]');
      try {
        const vehicle = await loadVehicle();
        const records = vehicle ? await loadRecords(vehicle.id) : [];
        const data = {
          schemaVersion: 1,
          contractVersion: api.contractVersion,
          mode: api.mode,
          exportedAt: new Date().toISOString(),
          vehicle,
          records,
          selectedQuestions: api.mode === 'live' ? [] : readSelectedQuestions(),
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = `chageun-data-${api.mode}-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.append(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        showMessage(status, '차량 정보와 입력 기록을 JSON 파일로 내보냈습니다. 파일은 이 기기에서 안전하게 보관하세요.');
      } catch (error) {
        showMessage(status, errorText(error));
      }
    });
  }

  // ───────────────────────── 대시보드 ─────────────────────────
  function renderVehicleSummary(summary, vehicle) {
    const generation = vehicle ? vehicle.generation : null;
    const name = vehicle ? [vehicle.manufacturer, vehicle.model, generation].filter(Boolean).join(' ') : '';
    const specs = vehicle
      ? [vehicle.year && `${vehicle.year}년식`, vehicle.engine, vehicle.fuel, vehicle.transmission].filter(Boolean)
      : [];
    summary.querySelector('[data-vehicle-label]').textContent = vehicle ? (api.mode === 'live' ? '내 차량 · 서버 자료' : '내 차량 (미리보기 저장)') : '차량 정보 없음';
    summary.querySelector('[data-vehicle-name]').textContent = vehicle ? name || '차량 정보 미확인' : '차량을 먼저 등록해 주세요';
    summary.querySelector('[data-vehicle-spec]').textContent = vehicle ? specs.join(' · ') || '세부 사양 미확인' : '';
    summary.querySelector('[data-vehicle-mileage]').textContent = numberText(vehicle ? vehicle.mileage : null);
    summary.querySelector('[data-vehicle-date]').textContent = textOrUnknown(vehicle ? vehicle.reference_date : null);
  }

  // 차량 조회가 실패하면 요약 영역도 오류 상태로 바꿔, "불러오는 중"이 계속 남지 않게 합니다.
  function renderVehicleError(summary, error) {
    summary.querySelector('[data-vehicle-label]').textContent = '차량 정보 오류';
    summary.querySelector('[data-vehicle-name]').textContent = '차량 정보를 불러오지 못했습니다';
    summary.querySelector('[data-vehicle-spec]').textContent = errorText(error);
    summary.querySelector('[data-vehicle-mileage]').textContent = '확인 불가';
    summary.querySelector('[data-vehicle-date]').textContent = '확인 불가';
  }

  // ───────────────────────── 대시보드 로그인 상태 (서버 모드) ─────────────────────────
  // 서버 모드에서만 /api/auth/me를 호출합니다. 공개 정보인 아이디만 표시하고, 아이디·비밀번호는 저장소나 로그에 남기지 않습니다.
  // 401은 로그인되지 않았거나 세션이 유효하지 않은 경우입니다. 서버 응답만으로는 둘을 구분할 수 없으므로 만료 안내를 붙이지 않습니다.
  function redirectToLogin() {
    window.location.assign(appPath('/login?required=1'));
  }

  async function initAccountStatus(box) {
    const message = box.querySelector('[data-account-message]');
    const userRow = box.querySelector('[data-account-user]');
    const usernameText = box.querySelector('[data-account-username]');
    const logoutButton = box.querySelector('[data-logout]');
    box.hidden = false;
    showMessage(message, '로그인 상태를 확인하는 중입니다.');
    try {
      const body = await api.auth.me();
      usernameText.textContent = body.data.username;
      userRow.hidden = false;
      showMessage(message, '');
      logoutButton.hidden = false;
      logoutButton.addEventListener('click', async () => {
        logoutButton.disabled = true;
        showMessage(message, '로그아웃하는 중입니다.');
        try {
          await api.auth.logout();
          document.querySelector('#main').replaceChildren();
          window.location.assign(appPath('/login'));
        } catch (error) {
          if (error && error.status === 401) {
            redirectToLogin();
            return;
          }
          logoutButton.disabled = false;
          showMessage(message, '로그아웃하지 못했습니다. 잠시 후 다시 시도해 주세요.');
        }
      });
      return true;
    } catch (error) {
      if (error && error.status === 401) {
        // 로그인되지 않았거나 세션이 유효하지 않은 상태입니다. 두 경우를 구분할 수 없으므로 로그인 필요 안내로 보냅니다.
        showMessage(message, '로그인이 필요합니다. 로그인 화면으로 이동합니다.');
        redirectToLogin();
        return false;
      }
      userRow.hidden = true;
      const offline = error && error.status === 0;
      showMessage(message, offline ? '서버에 연결하지 못해 로그인 상태를 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.' : '서버 오류로 로그인 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.');
      return false;
    }
  }

  async function initDashboard() {
    const summary = document.querySelector('[data-vehicle-summary]');
    const list = document.querySelector('[data-dashboard-records]');
    let summaryReady = false;
    if (api.mode === 'live') {
      const accountBox = document.querySelector('[data-account-status]');
      if (accountBox && !await initAccountStatus(accountBox)) {
        if (summary) renderVehicleError(summary, new Error('로그인 상태를 확인하지 못했습니다.'));
        if (list) list.textContent = '로그인 상태 확인 후 기록을 불러올 수 있습니다.';
        const content = document.querySelector('[data-management-content]');
        if (content) content.textContent = '로그인 상태 확인 후 관리 안내를 불러올 수 있습니다.';
        showMessage(document.querySelector('[data-demo-data-note]'), '로그인 상태를 확인하지 못했습니다.');
        return;
      }
    }
    try {
      const vehicle = await loadVehicle();
      if (summary) renderVehicleSummary(summary, vehicle);
      summaryReady = true;
      if (list) {
        list.replaceChildren();
        const records = vehicle ? await loadRecords(vehicle.id) : [];
        if (records.length === 0) {
          appendText(list, 'p', 'muted', '저장된 관리기록이 없습니다.');
        } else {
          appendText(list, 'p', 'record-count', `입력한 기록 ${records.length}건`);
          const ul = document.createElement('ul');
          ul.className = 'dashboard-record-list';
          for (const record of records.slice(0, 3)) {
            const row = document.createElement('li');
            appendText(row, 'span', 'badge', KIND_LABELS[record.kind] || '기록');
            appendText(row, 'strong', '', ITEM_LABELS[record.item_key] || '관리항목 미확인');
            appendText(row, 'small', 'muted', `${WORK_TYPE_LABELS[record.work_type] || '작업 유형 미확인'} · ${record.date || '날짜 미확인'} · ${textOrUnknown(record.source)}`);
            ul.append(row);
          }
          list.append(ul);
          if (records.length > 3) appendText(list, 'p', 'muted', `최근 3건을 표시했습니다. 나머지 ${records.length - 3}건은 타임라인에서 확인할 수 있습니다.`);
        }
      }
      if (api.mode === 'live') await initManagement(vehicle);
    } catch (error) {
      if (api.mode === 'live' && error.status === 401) redirectToLogin();
      showMessage(document.querySelector('[data-demo-data-note]'), errorText(error));
      const content = document.querySelector('[data-management-content]');
      if (content) content.textContent = '자료 조회에 실패해 관리 안내를 표시할 수 없습니다.';
      if (summary && !summaryReady) renderVehicleError(summary, error);
      if (list) {
        list.replaceChildren();
        appendText(list, 'p', 'muted', errorText(error));
      }
    }
  }

  async function initManagement(suppliedVehicle) {
    const content = document.querySelector('[data-management-content]');
    const questions = document.querySelector('[data-management-questions]');
    const requestedItemKey = content?.dataset.managementItem || null;
    const note = document.querySelector('[data-demo-data-note]');
    const controls = document.querySelector('[data-management-controls]');
    if (controls) controls.hidden = true;
    if (content) content.textContent = '관리 안내를 불러오는 중입니다.';
    if (questions) questions.replaceChildren();
    try {
      const vehicle = suppliedVehicle === undefined ? await loadVehicle() : suppliedVehicle;
      if (!vehicle) {
        if (content) {
          content.replaceChildren();
          appendText(content, 'p', '', '차량을 등록하면 적용 가능한 관리 안내와 확인할 질문을 살펴볼 수 있습니다.');
          const link = appendText(content, 'a', 'button primary', '차량 등록하기');
          link.href = appPath('/vehicle');
        }
        showMessage(note, '등록된 차량이 없습니다.');
        if (questions) questions.textContent = '차량 등록 후 확인 질문이 표시됩니다.';
        return;
      }
      const body = await api.management.get(vehicle.id);
      const allItems = Array.isArray(body.data.items) ? body.data.items : [];
      const items = requestedItemKey
        ? allItems.filter((item) => item.item_key === requestedItemKey)
        : allItems;
      showMessage(note, body.meta.calculation_mode === 'test_fixture'
        ? '가상 시험 기준으로 계산한 결과입니다. 실제 제조사 권장 주기가 아닙니다.'
        : body.meta.calculation_mode === 'candidate_rights_pending'
          ? '2021년형 K5 DL3 2.0 가솔린 G2.0 CVVL 후보 기준으로 계산했습니다. 사용 권리 확인 중이며, 기아가 차근의 계산·안내를 승인한 것은 아닙니다. 실제 부품 상태와 정비 필요 여부는 정비소에서 확인하세요.'
          : window.ChageunVehicleScope.notice(vehicle));
      if (content) content.replaceChildren();
      if (items.length === 0 && content) {
        appendText(content, 'p', '', '현재 차량에 적용할 수 있는 관리 안내가 없습니다. 차량 사양과 관리 기준을 확인해 주세요.');
      }
      for (const item of items) {
        if (content) {
          const row = appendText(content, 'article', 'maintenance-row', '');
          row.dataset.labels = item.labels.join('|');
          const main = appendText(row, 'div', 'item-main', '');
          const badges = appendText(main, 'div', 'badge-row', '');
          for (const label of item.labels) appendText(badges, 'span', 'badge', label);
          if (item.rights_review_pending) appendText(badges, 'span', 'badge unknown', item.rights_status_label || '사용 권리 확인 중');
          if (item.is_fixture) appendText(badges, 'span', 'badge unknown', '가상 시험 기준');
          const title = appendText(main, 'h3', '', '');
          const positionLabel = POSITION_LABELS[item.component_position];
          const itemActions = new Set(items.filter((candidate) => candidate.item_key === item.item_key).map((candidate) => candidate.action));
          const actionLabel = itemActions.size > 1 || item.condition_based ? ` · ${ACTION_LABELS[item.action] || '관리'}` : '';
          const titleText = `${ITEM_LABELS[item.item_key] || '관리항목'}${actionLabel}${positionLabel ? ` · ${positionLabel}` : ''}`;
          const link = appendText(title, 'a', '', titleText);
          link.href = appPath(`/items/${encodeURIComponent(item.item_key)}`);
          for (const reason of item.reasons) appendText(main, 'p', '', reason);
          if (Array.isArray(item.matched_severe_condition_codes) && item.matched_severe_condition_codes.length) {
            const appliedConditions = item.matched_severe_condition_codes.map(code => code + '번').join(' · ');
            appendText(main, 'p', 'muted', '적용한 가혹조건: ' + appliedConditions);
          }
          if (item.condition_based || (item.timing_status !== 'unknown' && item.timing_status !== 'unsupported' && item.action)) {
            const actionText = item.condition_based ? '안내 방식: 세부 가혹조건에 해당할 때 상태를 수시 점검하고 필요 시 정비' : `안내 방식: 정기 ${ACTION_LABELS[item.action]}`;
            appendText(main, 'p', 'muted', actionText);
          }
          appendText(main, 'p', 'muted', `거리 기준: ${formatMileage(item.next_mileage)} · 기간 기준: ${item.next_date || '미확인'}`);
          appendText(main, 'small', 'muted', `기준 출처: ${item.source || '미확정'} · 기준 확인일: ${item.checked_date || '미확인'}`);
          if (typeof item.source_url === 'string') {
            try {
              const sourceUrl = new URL(item.source_url);
              if (sourceUrl.protocol === 'https:' && sourceUrl.hostname === 'ownersmanual.kia.com') {
                const sourceLink = appendText(main, 'a', 'muted', '기아 공식 취급설명서 열기');
                sourceLink.href = sourceUrl.href;
                sourceLink.target = '_blank';
                sourceLink.rel = 'noopener noreferrer';
              }
            } catch (_) {
              // Invalid source URLs are omitted instead of becoming clickable links.
            }
          }
          if (item.missing_fields.length) {
            const labels = { rule: '적용 기준', records: '이전 관리 기록', 'vehicle.id': '차량 ID' };
            const missing = item.missing_fields.map((field) => FIELD_LABELS[field.replace(/^(vehicle|record)\./, '')] || labels[field] || field);
            appendText(main, 'p', 'muted', `부족한 정보: ${missing.join(' · ')}`);
          }
        }
        if (questions) {
          if (!Array.isArray(item.questions) || item.questions.length === 0) continue;
          const group = appendText(questions, 'article', 'question-section', '');
          const positionLabel = POSITION_LABELS[item.component_position];
          const itemActions = new Set(items.filter((candidate) => candidate.item_key === item.item_key).map((candidate) => candidate.action));
          const actionLabel = itemActions.size > 1 || item.condition_based ? ` · ${ACTION_LABELS[item.action] || '관리'}` : '';
          const title = `${ITEM_LABELS[item.item_key] || '관리항목'}${actionLabel}${positionLabel ? ` · ${positionLabel}` : ''}`;
          appendText(group, 'h2', '', title);
          for (const question of item.questions) appendText(group, 'p', '', question);
        }
      }
      document.querySelectorAll('.status-count[data-label]').forEach((counter) => {
        const count = items.filter((item) => Array.isArray(item.labels) && item.labels.includes(counter.dataset.label)).length;
        counter.replaceChildren(document.createTextNode(String(count)));
        appendText(counter, 'small', '', '개 항목');
      });
      if (controls && items.length > 0) controls.hidden = false;
    } catch (error) {
      if (error.status === 401) redirectToLogin();
      if (content) content.textContent = errorText(error);
      if (questions) questions.textContent = errorText(error);
      showMessage(note, '관리 안내를 불러오지 못했습니다.');
    }
  }

  // ───────────────────────── 공통 화면 동작 ─────────────────────────
  // 정비 결과·이력 화면: 차량이 없으면 먼저 등록하라고 안내합니다.
  const recordForm = document.querySelector('#record-form');
  if (recordForm) {
    guardedSubmit(recordForm, async () => {
      const vehicle = await loadVehicle();
      if (!vehicle) {
        const error = new api.ApiError({ status: 404, code: 'NOT_FOUND', message: '먼저 차량 정보를 저장해 주세요.' });
        throw error;
      }
      await api.records.create(vehicle.id, recordFromForm(recordForm));
      window.location.assign(appPath('/timeline'));
    });
  }

  const vehicleForm = document.querySelector('#vehicle-form');
  if (vehicleForm) {
    initVehicleForm(vehicleForm);
    guardedSubmit(vehicleForm, async () => {
      const payload = vehicleFromForm(vehicleForm);
      const current = await loadVehicle();
      if (current && api.mode === 'live') {
        if (vehicleForm.dataset.existingVehicle !== 'true') {
          throw new api.ApiError({ status: 409, code: 'CONFLICT', message: '이미 등록된 차량입니다. 화면을 새로고침해 주세요.' });
        }
        await api.vehicles.update(current.id, payload);
      } else if (current) {
        await api.vehicles.update(current.id, payload);
      } else {
        await api.vehicles.create(payload);
      }
      window.location.assign(appPath('/dashboard'));
    });
  }

  const timelineList = document.querySelector('[data-saved-records]');
  if (timelineList) {
    renderTimeline(timelineList, document.querySelector('[data-export-message]'));
  }

  const exportButton = document.querySelector('[data-export-data]');
  if (exportButton) bindExport(exportButton);

  if (document.querySelector('[data-vehicle-summary]') || document.querySelector('[data-dashboard-records]')) {
    initDashboard();
  } else if (api.mode === 'live' && (document.querySelector('[data-management-content]') || document.querySelector('[data-management-questions]'))) {
    initManagement();
  }

  // 대시보드 필터
  document.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      const selected = button.dataset.filter;
      document.querySelectorAll('[data-filter]').forEach((filter) => {
        const active = filter === button;
        filter.classList.toggle('active', active);
        filter.setAttribute('aria-pressed', String(active));
      });
      let visibleCount = 0;
      document.querySelectorAll('[data-labels]').forEach((row) => {
        row.hidden = selected !== '전체' && !row.dataset.labels.split('|').includes(selected);
        if (!row.hidden) visibleCount += 1;
      });
      document.querySelector('#filter-empty').hidden = visibleCount !== 0;
    });
  });

  // 브라우저가 사용하는 현지 날짜로 미래 날짜 입력을 제한합니다.
  const today = new Date();
  const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  document.querySelectorAll('.work-date').forEach((field) => { field.max = localDate; });
  const mileageReferenceDate = document.querySelector('#reference-date');
  if (mileageReferenceDate) mileageReferenceDate.max = localDate;

  // 질문 체크는 아직 이 브라우저에만 저장합니다. 서버 저장은 후속 범위입니다.
  const questionMessage = document.querySelector('[data-question-message]');
  const questionCheckboxes = document.querySelectorAll('[data-question-key]');
  if (questionCheckboxes.length) {
    const selectedQuestions = new Set(readSelectedQuestions());
    questionCheckboxes.forEach((checkbox) => {
      checkbox.checked = selectedQuestions.has(checkbox.dataset.questionKey);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) selectedQuestions.add(checkbox.dataset.questionKey);
        else selectedQuestions.delete(checkbox.dataset.questionKey);
        try {
          localStorage.setItem(QUESTION_STORAGE_KEY, JSON.stringify([...selectedQuestions]));
          showMessage(questionMessage, '질문 체크 상태를 이 브라우저에 저장했습니다. 정비 결과 기록은 별도로 입력해야 합니다.');
        } catch {
          showMessage(questionMessage, '브라우저에 저장하지 못했습니다. 체크 상태는 이번 화면에서만 유지됩니다.');
        }
      });
    });
  }

  // ───────────────────────── 로그인·회원가입 ─────────────────────────
  // 비밀번호는 입력칸에만 있고 저장소·로그에 남기지 않습니다. 실패해도 아이디 입력값은 그대로 둡니다.
  function initAuthForm(form) {
    const mode = form.dataset.authForm === 'register' ? 'register' : 'login';
    const message = form.querySelector('.form-message[role="status"]');
    const usernameInput = form.querySelector('#username');
    const passwordInput = form.querySelector('#password');
    const usernameError = form.querySelector('#username-error');
    const passwordError = form.querySelector('#password-error');
    let busy = false;

    function setFieldError(element, input, text) {
      if (!element) return;
      element.textContent = text || '';
      element.hidden = !text;
      if (input) input.setAttribute('aria-invalid', String(Boolean(text)));
    }

    function clearFieldErrors() {
      setFieldError(usernameError, usernameInput, '');
      setFieldError(passwordError, passwordInput, '');
    }

    function showAuthError(error) {
      const status = error && error.status;
      const fields = (error && error.fields) || {};
      if (fields.username) setFieldError(usernameError, usernameInput, fields.username);
      if (fields.password) setFieldError(passwordError, passwordInput, fields.password);
      let text;
      if (status === 401) {
        text = '아이디 또는 비밀번호가 올바르지 않습니다.';
      } else if (status === 409) {
        setFieldError(usernameError, usernameInput, '이미 사용 중인 아이디입니다.');
        text = '이미 사용 중인 아이디입니다. 다른 아이디를 입력해 주세요.';
      } else if (status === 403) {
        text = '보안 확인이 만료되었습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.';
      } else if (Object.keys(fields).length) {
        text = '입력을 확인해 주세요. 표시된 항목을 다시 확인해 주세요.';
      } else {
        text = (error && error.message) || '처리하지 못했습니다. 잠시 후 다시 시도해 주세요.';
      }
      showMessage(message, text);
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (busy) return;
      busy = true;
      clearFieldErrors();
      const username = usernameInput.value;
      const password = passwordInput.value;
      let navigating = false;
      lockForm(form, true);
      showMessage(message, mode === 'login' ? '로그인 확인 중입니다. 잠시만 기다려 주세요.' : '가입 요청 중입니다. 잠시만 기다려 주세요.');
      try {
        if (mode === 'login') {
          await api.auth.login(username, password);
          navigating = true;
          showMessage(message, api.mode === 'live' ? '로그인되었습니다. 대시보드로 이동합니다.' : '가상(mock) 로그인 처리했습니다. 대시보드로 이동합니다.');
          window.location.assign(appPath('/dashboard'));
        } else {
          await api.auth.register(username, password);
          passwordInput.value = '';
          showMessage(
            message,
            api.mode === 'live'
              ? '가입이 완료되었습니다. 로그인 화면에서 로그인해 주세요.'
              : '가상(mock) 응답으로 가입 처리했습니다. 실제 계정은 만들어지지 않았습니다.',
          );
        }
      } catch (error) {
        showAuthError(error);
      } finally {
        busy = false;
        if (!navigating) lockForm(form, false);
      }
    });
  }

  const authForm = document.querySelector('[data-auth-form]');
  if (authForm) initAuthForm(authForm);

})();
