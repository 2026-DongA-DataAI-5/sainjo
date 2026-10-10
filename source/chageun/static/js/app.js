// 차량·관리 기록·질문 체크를 이 브라우저에 저장하고 화면에 표시합니다. 서버 전송은 없습니다.
const VEHICLE_STORAGE_KEY = 'chageun.vehicle.v1';
const RECORD_STORAGE_KEY = 'chageun.records.v1';
const QUESTION_STORAGE_KEY = 'chageun.questions.v1';
const APP_BASE_PATH = document.documentElement.dataset.basePath || '';

function appPath(path) {
  return `${APP_BASE_PATH}${path.startsWith('/') ? path : `/${path}`}`;
}

function readSavedVehicle() {
  try {
    const value = localStorage.getItem(VEHICLE_STORAGE_KEY);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

function displayValue(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : '미확인';
}

function readSavedRecords() {
  try {
    const value = JSON.parse(localStorage.getItem(RECORD_STORAGE_KEY) || '[]');
    return Array.isArray(value) ? value.filter((record) => record && typeof record.id === 'string') : [];
  } catch {
    return [];
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

function formatMileage(value) {
  return value ? `${Number(value).toLocaleString('ko-KR')}km` : '주행거리 미확인';
}

function appendText(parent, tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function renderSavedRecords() {
  const list = document.querySelector('[data-saved-records]');
  if (!list) return;

  const records = readSavedRecords().sort((a, b) => {
    const aDate = a.date || a.savedAt || '';
    const bDate = b.date || b.savedAt || '';
    return bDate.localeCompare(aDate);
  });
  list.replaceChildren();
  if (records.length === 0) {
    appendText(list, 'p', 'muted', '아직 저장한 기록이 없습니다.');
    return;
  }

  for (const record of records) {
    const entry = document.createElement('article');
    entry.className = 'timeline-entry saved-entry';
    const date = appendText(entry, 'div', 'timeline-date', record.date || '날짜 미확인');
    appendText(date, 'span', '', formatMileage(record.mileage));
    const details = document.createElement('div');
    const tag = record.kind === 'maintenance_result' ? '정비 결과 입력' : '이전 이력 입력';
    appendText(details, 'span', 'badge', tag);
    appendText(details, 'span', 'badge', record.workType || '작업 유형 미확인');
    const title = document.createElement('h3');
    const itemLink = document.createElement('a');
    itemLink.href = appPath(`/items/${encodeURIComponent(record.itemKey || '')}`);
    itemLink.textContent = record.itemName || '관리항목 미확인';
    title.append(itemLink);
    details.append(title);
    appendText(details, 'p', '', record.result || '추가 메모 없음');
    const provenance = `출처: ${record.source || '미확인'} · 자료 확인일: ${record.checkedDate || '미확인'} · 저장일: ${record.savedAt || '미확인'}`;
    appendText(details, 'small', 'muted', provenance);
    appendText(details, 'small', 'record-limit-note', '사용자 입력 · 외부 자료와 자동 대조되지 않음');
    const removeButton = appendText(details, 'button', 'record-delete', '이 기록 삭제');
    removeButton.type = 'button';
    const confirmation = document.createElement('div');
    confirmation.className = 'delete-confirmation';
    confirmation.setAttribute('role', 'group');
    confirmation.setAttribute('aria-label', '기록 삭제 확인');
    confirmation.hidden = true;
    appendText(confirmation, 'span', '', '이 기록을 현재 브라우저에서 삭제할까요?');
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
    confirmButton.addEventListener('click', () => {
      try {
        localStorage.setItem(RECORD_STORAGE_KEY, JSON.stringify(readSavedRecords().filter((item) => item.id !== record.id)));
        renderSavedRecords();
      } catch {
        window.alert('기록을 삭제하지 못했습니다. 브라우저 저장 공간을 확인해 주세요.');
      }
    });
    entry.append(details);
    list.append(entry);
  }
}

const recordForm = document.querySelector('#record-form');
if (recordForm) {
  recordForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(recordForm).entries());
    const itemSelect = recordForm.elements.namedItem('item');
    const workTypeSelect = recordForm.elements.namedItem('work_type');
    const message = recordForm.querySelector('.form-message');
    const selectedItem = itemSelect.options[itemSelect.selectedIndex];
    const record = {
      id: window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      kind: recordForm.dataset.recordKind,
      itemKey: fields.item,
      itemName: selectedItem.textContent.trim(),
      workType: workTypeSelect.options[workTypeSelect.selectedIndex].textContent.trim(),
      date: fields.date,
      mileage: fields.mileage,
      result: fields.result.trim(),
      source: fields.source,
      checkedDate: fields.checked_date,
      savedAt: localDate,
    };

    try {
      localStorage.setItem(RECORD_STORAGE_KEY, JSON.stringify([...readSavedRecords(), record]));
      window.location.assign(appPath('/timeline'));
    } catch {
      message.textContent = '브라우저 저장 공간을 사용할 수 없습니다. 입력 내용은 저장되지 않았습니다.';
    }
  });
}

renderSavedRecords();

const vehicleForm = document.querySelector('#vehicle-form');
if (vehicleForm) {
  const savedVehicle = readSavedVehicle();
  const clearButton = document.querySelector('[data-clear-vehicle]');
  const clearConfirmation = document.querySelector('[data-clear-confirmation]');
  const message = vehicleForm.querySelector('.form-message');

  if (savedVehicle) {
    for (const [name, value] of Object.entries(savedVehicle)) {
      const field = vehicleForm.elements.namedItem(name);
      if (field && typeof value === 'string') field.value = value;
    }
    clearButton.hidden = false;
  }

  vehicleForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const vehicle = Object.fromEntries(new FormData(vehicleForm).entries());
    for (const [name, value] of Object.entries(vehicle)) vehicle[name] = value.trim();

    try {
      localStorage.setItem(VEHICLE_STORAGE_KEY, JSON.stringify(vehicle));
      window.location.assign(appPath('/dashboard'));
    } catch {
      message.textContent = '브라우저 저장 공간을 사용할 수 없습니다. 브라우저 설정을 확인해 주세요.';
    }
  });

  clearButton.addEventListener('click', () => {
    clearConfirmation.hidden = false;
    document.querySelector('[data-confirm-clear]').focus();
  });

  document.querySelector('[data-cancel-clear]').addEventListener('click', () => {
    clearConfirmation.hidden = true;
    clearButton.focus();
  });

  document.querySelector('[data-confirm-clear]').addEventListener('click', () => {
    try {
      localStorage.removeItem(VEHICLE_STORAGE_KEY);
      vehicleForm.reset();
      clearButton.hidden = true;
      clearConfirmation.hidden = true;
      message.textContent = '이 브라우저에 저장한 차량 정보를 삭제했습니다.';
    } catch {
      message.textContent = '저장 정보를 삭제할 수 없습니다. 브라우저 설정을 확인해 주세요.';
    }
  });
}

const dashboardVehicle = document.querySelector('[data-vehicle-summary]');
const savedVehicle = readSavedVehicle();
if (dashboardVehicle && savedVehicle) {
  const generation = savedVehicle.generation === 'unknown' ? '' : savedVehicle.generation;
  const name = [savedVehicle.manufacturer, savedVehicle.model, generation].filter(Boolean).join(' ');
  const specifications = [
    savedVehicle.year && `${savedVehicle.year}년식`,
    savedVehicle.engine,
    savedVehicle.fuel,
    savedVehicle.transmission,
  ].filter(Boolean);

  dashboardVehicle.querySelector('[data-vehicle-label]').textContent = '이 브라우저에 저장한 차량';
  dashboardVehicle.querySelector('[data-vehicle-name]').textContent = name || '차량 정보 미확인';
  dashboardVehicle.querySelector('[data-vehicle-spec]').textContent = specifications.join(' · ') || '세부 사양 미확인';
  dashboardVehicle.querySelector('[data-vehicle-mileage]').textContent = displayValue(savedVehicle.mileage);
  dashboardVehicle.querySelector('[data-vehicle-date]').textContent = displayValue(savedVehicle.reference_date);
}

const dashboardRecords = document.querySelector('[data-dashboard-records]');
if (dashboardRecords) {
  const records = readSavedRecords().sort((a, b) => (b.date || b.savedAt || '').localeCompare(a.date || a.savedAt || ''));
  dashboardRecords.replaceChildren();
  if (records.length === 0) {
    appendText(dashboardRecords, 'p', 'muted', '저장된 관리기록이 없습니다.');
  } else {
    appendText(dashboardRecords, 'p', 'record-count', `이 브라우저에 입력한 기록 ${records.length}건`);
    const list = document.createElement('ul');
    list.className = 'dashboard-record-list';
    for (const record of records.slice(0, 3)) {
      const row = document.createElement('li');
      const work = record.kind === 'maintenance_result' ? '정비 결과' : '이전 이력';
      appendText(row, 'span', 'badge', work);
      appendText(row, 'strong', '', record.itemName || '관리항목 미확인');
      appendText(row, 'small', 'muted', `${record.workType || '작업 유형 미확인'} · ${record.date || '날짜 미확인'} · ${record.source || '출처 미확인'}`);
      list.append(row);
    }
    dashboardRecords.append(list);
    if (records.length > 3) appendText(dashboardRecords, 'p', 'muted', `최근 3건을 표시했습니다. 나머지 ${records.length - 3}건은 타임라인에서 확인할 수 있습니다.`);
  }
}

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

// 브라우저가 사용하는 현지 날짜로 미래 정비일 입력을 제한합니다.
const today = new Date();
const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
document.querySelectorAll('.work-date').forEach((field) => { field.max = localDate; });
const mileageReferenceDate = document.querySelector('#reference-date');
if (mileageReferenceDate) mileageReferenceDate.max = localDate;

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
        if (questionMessage) questionMessage.textContent = '질문 체크 상태를 이 브라우저에 저장했습니다. 정비 결과 기록은 별도로 입력해야 합니다.';
      } catch {
        if (questionMessage) questionMessage.textContent = '브라우저에 저장하지 못했습니다. 체크 상태는 이번 화면에서만 유지됩니다.';
      }
    });
  });
}

const exportButton = document.querySelector('[data-export-data]');
if (exportButton) {
  exportButton.addEventListener('click', () => {
    const exportMessage = document.querySelector('[data-export-message]');
    const data = {
      schemaVersion: 1,
      exportedAt: new Date().toISOString(),
      vehicle: readSavedVehicle(),
      records: readSavedRecords(),
      selectedQuestions: readSelectedQuestions(),
    };
    try {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `chageun-data-${localDate}.json`;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      exportMessage.textContent = '차량 정보·입력 기록·선택한 질문을 JSON 파일로 내보냈습니다. 파일은 이 기기에서 안전하게 보관하세요.';
    } catch {
      exportMessage.textContent = '파일을 만들지 못했습니다. 브라우저 다운로드 설정을 확인해 주세요.';
    }
  });
}

