// 차근 API 통신 모듈 (공통 계약 v1.0)
// - mode=mock: api_examples.json과 같은 구조의 가짜 응답을 브라우저 안에서 만듭니다. 서버로 보내지 않습니다.
// - mode=live: 같은 Flask 출처의 /api로 요청합니다. (<html data-api-mode="live">일 때만)
// - 요청이 실패해도 mock ↔ live 자동 전환은 하지 않습니다.
// - 관리 판단(교환 시기 계산)은 여기서 하지 않습니다. 서버 응답을 그대로 전달합니다.
(function () {
  'use strict';

  const CONTRACT_VERSION = '1.0';
  const MODE = document.documentElement.dataset.apiMode === 'live' ? 'live' : 'mock';
  const UNSAFE_METHODS = new Set(['POST', 'PATCH', 'DELETE']);

  const DEFAULT_MESSAGES = {
    0: '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    400: '입력을 확인해 주세요',
    401: '로그인이 필요합니다. 다시 로그인해 주세요.',
    403: '보안 확인이 만료되었습니다. 다시 시도해 주세요.',
    404: '요청한 정보를 찾을 수 없습니다.',
    409: '이미 등록된 정보가 있습니다.',
    500: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
  };

  class ApiError extends Error {
    constructor({ status = 0, code = 'NETWORK_ERROR', message, fields = {}, uncertain = false } = {}) {
      super(message || DEFAULT_MESSAGES[status] || DEFAULT_MESSAGES[500]);
      this.name = 'ApiError';
      this.status = status;
      this.code = code;
      this.fields = fields && typeof fields === 'object' ? fields : {};
      // POST/PATCH/DELETE 응답을 받지 못해 서버 반영 여부를 알 수 없는 경우 true
      this.uncertain = uncertain;
    }
  }

  // ───────────────────────── 입력값 변환 도우미 ─────────────────────────
  // 화면 입력(문자열)을 계약 자료형으로 바꿉니다. 빈 입력만 null이 됩니다.
  const convert = {
    text(value) {
      if (value === null || value === undefined) return null;
      const text = String(value).trim();
      return text === '' ? null : text;
    },
    int(value) {
      const text = convert.text(value);
      if (text === null) return null;
      return /^-?\d+$/.test(text) ? Number(text) : text; // 숫자가 아니면 그대로 보내 서버가 400으로 알려 줍니다.
    },
    date(value) {
      return convert.text(value);
    },
  };

  function toId(value) {
    const id = Number(value);
    if (!Number.isInteger(id) || id <= 0) {
      throw new ApiError({ status: 400, code: 'VALIDATION_ERROR', message: '잘못된 ID입니다.' });
    }
    return id;
  }

  // ───────────────────────── live: 실제 서버 ─────────────────────────
  let csrfToken = null;

  async function fetchCsrfToken() {
    const body = await liveRequest('GET', '/api/auth/csrf');
    csrfToken = body.data.csrf_token;
    return csrfToken;
  }

  async function liveRequest(method, path, payload) {
    const headers = { Accept: 'application/json' };
    const init = { method, headers, credentials: 'same-origin' };
    if (payload !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(payload);
    }
    if (UNSAFE_METHODS.has(method)) {
      headers['X-CSRF-Token'] = csrfToken || (await fetchCsrfToken());
    }

    let response;
    try {
      response = await fetch(path, init);
    } catch {
      throw new ApiError({ status: 0, code: 'NETWORK_ERROR', uncertain: UNSAFE_METHODS.has(method) });
    }

    let body = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }

    if (!response.ok) {
      if (response.status === 403) csrfToken = null; // 다음 변경 요청 때 토큰을 다시 받습니다.
      const error = (body && body.error) || {};
      throw new ApiError({
        status: response.status,
        code: error.code || (response.status >= 500 ? 'INTERNAL_ERROR' : 'UNKNOWN_ERROR'),
        message: error.message,
        fields: error.fields,
      });
    }
    if (!body || !Object.prototype.hasOwnProperty.call(body, 'data')) {
      throw new ApiError({ status: response.status, code: 'INVALID_RESPONSE', message: '서버 응답 형식이 올바르지 않습니다.' });
    }
    return body;
  }

  // ───────────────────────── mock: 가짜 서버 ─────────────────────────
  // 이 탭의 sessionStorage에만 보관합니다. 기존 localStorage 자료와 섞지 않습니다.
  const MOCK_STORAGE_KEY = 'chageun.mock-api.v1';
  const MOCK_USER = { id: 1, username: 'member_a' };
  let memoryStore = null;

  function emptyStore() {
    return { user: { ...MOCK_USER }, vehicles: [], records: [], nextId: { vehicle: 1, record: 1 }, calculation: 'unavailable', failNext: null };
  }

  // memoryStore는 sessionStorage 저장이 실패했을 때만 채워집니다.
  // 값이 있으면 오래된 sessionStorage 값보다 항상 먼저 사용합니다.
  function loadStore() {
    if (memoryStore) return memoryStore;
    try {
      const saved = JSON.parse(sessionStorage.getItem(MOCK_STORAGE_KEY) || 'null');
      if (saved && Array.isArray(saved.vehicles)) return saved;
    } catch {
      // sessionStorage를 읽을 수 없으면 빈 상태에서 시작합니다.
    }
    return emptyStore();
  }

  function saveStore(store) {
    try {
      sessionStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(store));
      memoryStore = null; // 저장에 성공했으므로 sessionStorage가 기준입니다.
    } catch {
      // 저장에 실패하면 메모리 사본을 우선 사용합니다(새로고침 시 사라짐).
      memoryStore = store;
    }
  }

  function todayKst() {
    return new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
  }

  function isValidDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  const VEHICLE_SCHEMA = {
    manufacturer: { type: 'string', max: 40 },
    model: { type: 'string', max: 40 },
    generation: { type: 'enum', values: ['DL3', 'JF'] },
    year: { type: 'int', min: 1900, max: 2035 },
    engine: { type: 'string', max: 60 },
    fuel: { type: 'string', max: 30 },
    transmission: { type: 'string', max: 40 },
    mileage: { type: 'int', min: 0, max: 1000000 },
    reference_date: { type: 'date' },
    conditions: { type: 'enum', values: ['normal', 'severe', 'unknown'], required: true, defaultValue: 'unknown' },
  };

  const RECORD_SCHEMA = {
    kind: { type: 'enum', values: ['previous_history', 'maintenance_result'], required: true },
    item_key: { type: 'enum', values: ['engine-oil'], required: true },
    work_type: { type: 'enum', values: ['inspection', 'replacement', 'unknown'], required: true },
    date: { type: 'date' },
    mileage: { type: 'int', min: 0, max: 1000000 },
    result: { type: 'string', max: 2000 },
    source: { type: 'string', max: 100 },
    checked_date: { type: 'date' },
  };

  function checkField(rule, value) {
    if (value === null) return rule.required ? '비워 둘 수 없는 항목입니다.' : null;
    if (rule.type === 'string') {
      if (typeof value !== 'string') return '글자로 입력해 주세요.';
      if (value.length > rule.max) return `${rule.max}자 이하로 입력해 주세요.`;
    } else if (rule.type === 'int') {
      if (typeof value !== 'number' || !Number.isInteger(value)) return '정수로 입력해 주세요.';
      if (value < rule.min || value > rule.max) return `${rule.min.toLocaleString('ko-KR')}~${rule.max.toLocaleString('ko-KR')} 사이로 입력해 주세요.`;
    } else if (rule.type === 'date') {
      if (!isValidDate(value)) return 'YYYY-MM-DD 형식의 날짜를 입력해 주세요.';
      if (value > todayKst()) return '오늘 이후 날짜는 입력할 수 없습니다.';
    } else if (rule.type === 'enum') {
      if (!rule.values.includes(value)) return '선택할 수 없는 값입니다.';
    }
    return null;
  }

  function validate(schema, body, { partial }) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      throw mockError(400, 'VALIDATION_ERROR', '요청 형식이 올바르지 않습니다.');
    }
    const fields = {};
    for (const key of Object.keys(body)) {
      if (!Object.prototype.hasOwnProperty.call(schema, key)) fields[key] = '허용되지 않은 항목입니다.';
    }
    if (partial && Object.keys(body).length === 0) {
      throw mockError(400, 'VALIDATION_ERROR', '변경할 항목이 없습니다.');
    }
    const value = {};
    for (const [key, rule] of Object.entries(schema)) {
      if (!Object.prototype.hasOwnProperty.call(body, key)) {
        if (partial) continue;
        if (rule.defaultValue !== undefined) value[key] = rule.defaultValue;
        else if (rule.required) fields[key] = '필수 항목입니다.';
        else value[key] = null;
        continue;
      }
      const problem = checkField(rule, body[key]);
      if (problem) fields[key] = problem;
      else value[key] = body[key];
    }
    if (Object.keys(fields).length) throw mockError(400, 'VALIDATION_ERROR', undefined, fields);
    return value;
  }

  function mockError(status, code, message, fields = {}) {
    return new ApiError({ status, code, message, fields });
  }

  function envelope(data, extraMeta = {}) {
    return { data, meta: { contract_version: CONTRACT_VERSION, mode: 'mock', calculation_mode: 'none', ...extraMeta } };
  }

  function sortRecords(records) {
    return [...records].sort((a, b) => {
      if (a.date !== b.date) {
        if (!a.date) return 1;
        if (!b.date) return -1;
        return b.date.localeCompare(a.date);
      }
      if (a.created_at !== b.created_at) return b.created_at.localeCompare(a.created_at);
      return b.id - a.id;
    });
  }

  function ownedVehicle(store, id) {
    const vehicle = store.vehicles.find((entry) => entry.id === id);
    if (!vehicle) throw mockError(404, 'NOT_FOUND');
    return vehicle;
  }

  function ownedRecord(store, id) {
    const record = store.records.find((entry) => entry.id === id);
    if (!record) throw mockError(404, 'NOT_FOUND');
    return record;
  }

  // 관리 안내 mock: 기준 계산은 하지 않고 계약 예시와 같은 형태만 돌려줍니다.
  function mockManagement(store, vehicleId) {
    const hasKnownWork = store.records.some(
      (record) => record.vehicle_id === vehicleId && record.item_key === 'engine-oil' && record.work_type !== 'unknown',
    );
    if (store.calculation === 'test_fixture') {
      return envelope(
        {
          vehicle_id: vehicleId,
          items: [{
            item_key: 'engine-oil',
            history_status: hasKnownWork ? 'recorded' : 'unknown',
            timing_status: 'upcoming',
            labels: [hasKnownWork ? '확인된 관리 이력' : '이력 미확인', '향후 관리 예정'],
            next_mileage: 30000,
            next_date: '2026-07-31',
            reasons: ['가상 기준의 거리·기간 모두 미도달'],
            missing_fields: [],
            rule_id: 'TEST_ONLY_OIL_001',
            source: '가상 테스트 기준 - 실제 제조사 기준 아님',
            checked_date: '2026-06-01',
            questions: ['마지막 교환 기록과 운행조건을 함께 확인해 주실 수 있나요?'],
            is_fixture: true,
          }],
        },
        { calculation_mode: 'test_fixture' },
      );
    }
    return envelope(
      {
        vehicle_id: vehicleId,
        items: [{
          item_key: 'engine-oil',
          history_status: hasKnownWork ? 'recorded' : 'unknown',
          timing_status: 'unknown',
          labels: [hasKnownWork ? '확인된 관리 이력' : '이력 미확인'],
          next_mileage: null,
          next_date: null,
          reasons: ['실제 적용 기준이 미확정입니다.'],
          missing_fields: ['rule'],
          rule_id: null,
          source: null,
          checked_date: null,
          questions: ['마지막 교환 기록과 운행조건을 함께 확인해 주실 수 있나요?'],
          is_fixture: false,
        }],
      },
      { calculation_mode: 'unavailable' },
    );
  }

  function handleMock(method, rawPath, payload) {
    const store = loadStore();
    const url = new URL(rawPath, window.location.origin);
    const path = url.pathname.replace(/\/+$/, '');
    let match;

    // 오류 화면 시험용: ChageunApi.mock.failNext(...)
    if (store.failNext) {
      const failure = store.failNext;
      store.failNext = null;
      saveStore(store);
      if (failure === 'network') throw new ApiError({ status: 0, code: 'NETWORK_ERROR', uncertain: UNSAFE_METHODS.has(method) });
      throw mockError(Number(failure) || 500, Number(failure) === 401 ? 'AUTH_REQUIRED' : 'INTERNAL_ERROR');
    }

    // 인증
    if (method === 'GET' && path === '/api/auth/csrf') return envelope({ csrf_token: 'DEV_EXAMPLE_NOT_REAL_TOKEN' });
    if (method === 'POST' && (path === '/api/auth/login' || path === '/api/auth/register')) {
      const username = payload && payload.username;
      const password = payload && payload.password;
      const fields = {};
      if (typeof username !== 'string' || !/^[a-z0-9_]{3,30}$/.test(username)) fields.username = '영문 소문자·숫자·밑줄 3~30자로 입력해 주세요.';
      if (typeof password !== 'string' || password.length < 8 || password.length > 128) fields.password = '8~128자로 입력해 주세요.';
      if (Object.keys(fields).length) throw mockError(400, 'VALIDATION_ERROR', undefined, fields);
      const user = { id: 1, username };
      if (path === '/api/auth/login') {
        store.user = user;
        saveStore(store);
        return envelope(user);
      }
      return { ...envelope(user), status: 201 };
    }
    if (method === 'POST' && path === '/api/auth/logout') {
      store.user = null;
      saveStore(store);
      return envelope({ logged_out: true });
    }

    // 이하 로그인 필요
    if (!store.user) throw mockError(401, 'AUTH_REQUIRED');
    if (method === 'GET' && path === '/api/auth/me') return envelope({ ...store.user });

    if (path === '/api/vehicles') {
      if (method === 'GET') return envelope(store.vehicles.map((vehicle) => ({ ...vehicle })));
      if (method === 'POST') {
        const value = validate(VEHICLE_SCHEMA, payload, { partial: false });
        if (store.vehicles.length > 0) throw mockError(409, 'CONFLICT', '이 계정에는 이미 등록된 차량이 있습니다.');
        const vehicle = { id: store.nextId.vehicle++, ...value, created_at: new Date().toISOString() };
        store.vehicles.push(vehicle);
        saveStore(store);
        return { ...envelope({ ...vehicle }), status: 201 };
      }
    }

    if ((match = path.match(/^\/api\/vehicles\/(\d+)$/))) {
      const vehicle = ownedVehicle(store, Number(match[1]));
      if (method === 'GET') return envelope({ ...vehicle });
      if (method === 'PATCH') {
        Object.assign(vehicle, validate(VEHICLE_SCHEMA, payload, { partial: true }));
        saveStore(store);
        return envelope({ ...vehicle });
      }
    }

    if ((match = path.match(/^\/api\/vehicles\/(\d+)\/records$/))) {
      const vehicle = ownedVehicle(store, Number(match[1]));
      if (method === 'GET') {
        const page = Number(url.searchParams.get('page') || 1);
        const pageSize = Number(url.searchParams.get('page_size') || 20);
        if (!Number.isInteger(page) || page < 1 || !Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
          throw mockError(400, 'VALIDATION_ERROR', 'page 또는 page_size 값이 올바르지 않습니다.');
        }
        const all = sortRecords(store.records.filter((record) => record.vehicle_id === vehicle.id));
        const items = all.slice((page - 1) * pageSize, page * pageSize).map((record) => ({ ...record }));
        return envelope(items, { pagination: { page, page_size: pageSize, total: all.length } });
      }
      if (method === 'POST') {
        const value = validate(RECORD_SCHEMA, payload, { partial: false });
        const record = { id: store.nextId.record++, vehicle_id: vehicle.id, ...value, created_at: new Date().toISOString() };
        store.records.push(record);
        saveStore(store);
        return { ...envelope({ ...record }), status: 201 };
      }
    }

    if ((match = path.match(/^\/api\/records\/(\d+)$/))) {
      const record = ownedRecord(store, Number(match[1]));
      if (method === 'PATCH') {
        Object.assign(record, validate(RECORD_SCHEMA, payload, { partial: true }));
        saveStore(store);
        return envelope({ ...record });
      }
      if (method === 'DELETE') {
        store.records = store.records.filter((entry) => entry.id !== record.id);
        saveStore(store);
        return envelope({ id: record.id, deleted: true });
      }
    }

    if ((match = path.match(/^\/api\/vehicles\/(\d+)\/management$/)) && method === 'GET') {
      const vehicle = ownedVehicle(store, Number(match[1]));
      return mockManagement(store, vehicle.id);
    }

    throw mockError(404, 'NOT_FOUND');
  }

  function mockRequest(method, path, payload) {
    // 실제 통신처럼 잠깐 기다립니다. (버튼 잠금·로딩 표시 시험용)
    return new Promise((resolve, reject) => {
      window.setTimeout(() => {
        try {
          const body = handleMock(method, path, payload === undefined ? undefined : JSON.parse(JSON.stringify(payload)));
          delete body.status;
          resolve(body);
        } catch (error) {
          reject(error instanceof ApiError ? error : new ApiError({ status: 500, code: 'INTERNAL_ERROR' }));
        }
      }, 300);
    });
  }

  // ───────────────────────── 공통 진입점 ─────────────────────────
  function request(method, path, payload) {
    return MODE === 'live' ? liveRequest(method, path, payload) : mockRequest(method, path, payload);
  }

  const api = {
    mode: MODE,
    contractVersion: CONTRACT_VERSION,
    ApiError,
    convert,

    get: (path) => request('GET', path),
    post: (path, payload) => request('POST', path, payload),
    patch: (path, payload) => request('PATCH', path, payload),
    del: (path) => request('DELETE', path),

    auth: {
      async login(username, password) {
        const body = await request('POST', '/api/auth/login', { username, password });
        csrfToken = null; // 로그인 성공 후 토큰을 다시 발급받습니다.
        return body;
      },
      async logout() {
        const body = await request('POST', '/api/auth/logout');
        csrfToken = null;
        return body;
      },
      register: (username, password) => request('POST', '/api/auth/register', { username, password }),
      me: () => request('GET', '/api/auth/me'),
    },

    vehicles: {
      list: () => request('GET', '/api/vehicles'),
      create: (payload) => request('POST', '/api/vehicles', payload),
      get: async (id) => request('GET', `/api/vehicles/${toId(id)}`),
      update: async (id, payload) => request('PATCH', `/api/vehicles/${toId(id)}`, payload),
    },

    records: {
      list: async (vehicleId, { page = 1, pageSize = 20 } = {}) =>
        request('GET', `/api/vehicles/${toId(vehicleId)}/records?page=${page}&page_size=${pageSize}`),
      create: async (vehicleId, payload) => request('POST', `/api/vehicles/${toId(vehicleId)}/records`, payload),
      update: async (id, payload) => request('PATCH', `/api/records/${toId(id)}`, payload),
      remove: async (id) => request('DELETE', `/api/records/${toId(id)}`),
    },

    management: {
      get: async (vehicleId) => request('GET', `/api/vehicles/${toId(vehicleId)}/management`),
    },

    // 개발용 mock 조작 (live 모드에서는 동작하지 않습니다)
    mock: {
      reset() {
        memoryStore = null;
        try { sessionStorage.removeItem(MOCK_STORAGE_KEY); } catch { /* 무시 */ }
      },
      state: () => JSON.parse(JSON.stringify(loadStore())),
      setLoggedIn(loggedIn) {
        const store = loadStore();
        store.user = loggedIn ? { ...MOCK_USER } : null;
        saveStore(store);
      },
      // 'unavailable'(기본) 또는 'test_fixture'
      setCalculation(mode) {
        const store = loadStore();
        store.calculation = mode === 'test_fixture' ? 'test_fixture' : 'unavailable';
        saveStore(store);
      },
      // 다음 요청 한 번을 실패시킵니다: 'network' | 401 | 403 | 404 | 500
      failNext(kind) {
        const store = loadStore();
        store.failNext = kind;
        saveStore(store);
      },
    },
  };

  window.ChageunApi = Object.freeze(api);
})();
