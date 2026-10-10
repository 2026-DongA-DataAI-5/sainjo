// 차량·관리 기록 화면을 API 클라이언트(ChageunApi)에 연결합니다.
// 현재는 mock 모드입니다. 서버 연결 후에도 같은 호출을 사용하고, mode만 live로 바뀝니다.
// 판단 로직(교환 시기 계산)은 여기에 두지 않습니다. 서버 응답을 그대로 표시합니다.
(function () {
  'use strict';

  const api = window.ChageunApi;
  const QUESTION_STORAGE_KEY = 'chageun.questions.v1';
  const APP_BASE_PATH = document.documentElement.dataset.basePath || '';

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
    conditions: '운행조건',
    kind: '기록 종류',
    item_key: '관리항목',
    item: '관리항목',
    work_type: '작업 유형',
    date: '정비·점검일',
    result: '기록 내용',
    source: '출처',
    checked_date: '자료 확인일',
  };
  const WORK_TYPE_LABELS = { inspection: '점검', replacement: '교환', unknown: '작업 유형 미확인' };
  const KIND_LABELS = { previous_history: '이전 이력 입력', maintenance_result: '정비 결과 입력' };
  const ITEM_LABELS = { 'engine-oil': '엔진 오일·오일필터', 'air-filter': '엔진 에어클리너 필터', coolant: '냉각수' };

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

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.idleLabel = button.textContent;
      button.textContent = label;
      button.disabled = true;
    } else {
      button.textContent = button.dataset.idleLabel || button.textContent;
      button.disabled = false;
    }
  }

  // 제출 버튼을 잠그고 한 번에 한 요청만 보냅니다. 실패하면 입력은 그대로 남깁니다.
  function guardedSubmit(form, handler) {
    let busy = false;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (busy) return;
      busy = true;
      const button = form.querySelector('button[type="submit"]');
      const message = form.querySelector('.form-message');
      setBusy(button, true, '저장 중…');
      showMessage(message, '');
      try {
        await handler();
      } catch (error) {
        showMessage(message, errorText(error));
      } finally {
        busy = false;
        setBusy(button, false);
      }
    });
  }

  async function loadVehicle() {
    const body = await api.vehicles.list();
    return body.data[0] || null;
  }

  async function loadRecords(vehicleId) {
    const body = await api.records.list(vehicleId, { page: 1, pageSize: 100 });
    return body.data;
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
      conditions: form.querySelector('input[name="conditions"]:checked')?.value || 'unknown',
    };
  }

  function fillVehicleForm(form, vehicle) {
    for (const name of ['manufacturer', 'model', 'generation', 'year', 'engine', 'fuel', 'transmission', 'mileage', 'reference_date']) {
      const field = form.elements.namedItem(name);
      const raw = vehicle[name];
      if (name === 'generation') field.value = raw || 'unknown';
      else field.value = raw === null || raw === undefined ? '' : String(raw);
    }
    const condition = form.querySelector(`input[name="conditions"][value="${vehicle.conditions}"]`);
    if (condition) condition.checked = true;
  }

  async function initVehicleForm(form) {
    try {
      const vehicle = await loadVehicle();
      if (vehicle) fillVehicleForm(form, vehicle);
    } catch (error) {
      showMessage(form.querySelector('.form-message'), errorText(error));
    }
  }

  // ───────────────────────── 관리 기록 ─────────────────────────
  function recordFromForm(form) {
    const value = (name) => form.elements.namedItem(name).value;
    return {
      kind: form.dataset.recordKind,
      item_key: value('item'),
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
    appendText(details, 'p', '', record.result || '추가 메모 없음');
    const savedAt = typeof record.created_at === 'string' ? record.created_at.slice(0, 16).replace('T', ' ') : '미확인';
    appendText(details, 'small', 'muted', `출처: ${textOrUnknown(record.source)} · 자료 확인일: ${record.checked_date || '미확인'} · 등록: ${savedAt}`);
    appendText(details, 'small', 'record-limit-note', '사용자 입력 · 외부 자료와 자동 대조되지 않음');

    const removeButton = appendText(details, 'button', 'record-delete', '이 기록 삭제');
    removeButton.type = 'button';
    const confirmation = document.createElement('div');
    confirmation.className = 'delete-confirmation';
    confirmation.setAttribute('role', 'group');
    confirmation.setAttribute('aria-label', '기록 삭제 확인');
    confirmation.hidden = true;
    appendText(confirmation, 'span', '', '이 기록을 삭제할까요? 삭제하면 서버 기록에서도 사라집니다.');
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
      setBusy(confirmButton, true, '삭제 중…');
      cancelButton.disabled = true;
      try {
        await api.records.remove(record.id);
        onChanged();
      } catch (error) {
        // 삭제 실패 시 항목은 그대로 둡니다. 응답을 못 받았다면 목록을 다시 불러옵니다.
        showMessage(status, errorText(error));
        setBusy(confirmButton, false);
        cancelButton.disabled = false;
        if (error && error.uncertain) onChanged();
      }
    });

    entry.append(details);
    return entry;
  }

  async function renderTimeline(list, status) {
    list.replaceChildren();
    try {
      const vehicle = await loadVehicle();
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
          selectedQuestions: readSelectedQuestions(),
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
    summary.querySelector('[data-vehicle-label]').textContent = vehicle ? '내 차량 (미리보기 저장)' : '차량 정보 없음';
    summary.querySelector('[data-vehicle-name]').textContent = vehicle ? name || '차량 정보 미확인' : '차량을 먼저 등록해 주세요';
    summary.querySelector('[data-vehicle-spec]').textContent = vehicle ? specs.join(' · ') || '세부 사양 미확인' : '';
    summary.querySelector('[data-vehicle-mileage]').textContent = numberText(vehicle ? vehicle.mileage : null);
    summary.querySelector('[data-vehicle-date]').textContent = textOrUnknown(vehicle ? vehicle.reference_date : null);
  }

  async function initDashboard() {
    const summary = document.querySelector('[data-vehicle-summary]');
    const list = document.querySelector('[data-dashboard-records]');
    try {
      const vehicle = await loadVehicle();
      if (summary) renderVehicleSummary(summary, vehicle);
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
    } catch (error) {
      if (list) {
        list.replaceChildren();
        appendText(list, 'p', 'muted', errorText(error));
      }
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
      if (current) await api.vehicles.update(current.id, payload);
      else await api.vehicles.create(payload);
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
})();
