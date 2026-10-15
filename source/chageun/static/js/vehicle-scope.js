// 판단을 수행하지 않고, 현재 차량 사양과 고정된 안내 범위의 일치 여부만 설명합니다.
(function exposeVehicleScope(root, factory) {
  const scope = factory();
  if (typeof module === 'object' && module.exports) module.exports = scope;
  else root.ChageunVehicleScope = scope;
}(globalThis, function createVehicleScope() {
  'use strict';

  const TARGET = Object.freeze({
    manufacturer: '기아',
    model: 'K5',
    generation: 'DL3',
    year: 2021,
    engine: 'G2.0 CVVL',
    fuel: '가솔린',
    transmission: '자동',
  });
  const FIELD_LABELS = Object.freeze({
    manufacturer: '제조사',
    model: '모델',
    generation: '세대',
    year: '연식',
    engine: '엔진',
    fuel: '연료',
    transmission: '변속기',
  });
  const FIELDS = Object.keys(TARGET);
  const SCOPE_NAME = '국내 판매 2021년형 기아 K5 DL3 · 2.0 가솔린 · G2.0 CVVL · 자동변속기';

  function notice(vehicle) {
    const missing = FIELDS.filter((field) => {
      const value = vehicle && vehicle[field];
      return value === null || value === undefined || (typeof value === 'string' && !value.trim());
    });
    if (missing.length) {
      const labels = missing.map((field) => FIELD_LABELS[field]);
      return `관리 기준 검토 범위는 ${SCOPE_NAME}입니다. 차량의 ${labels.join('·')} 정보가 없어 적용 여부를 확인할 수 없습니다.`;
    }

    const matches = FIELDS.every((field) => vehicle[field] === TARGET[field]);
    if (!matches) {
      return `관리 기준 검토 범위는 ${SCOPE_NAME}입니다. 현재 차량 사양은 범위 밖이라 이 기준을 적용하지 않습니다. 차량 등록과 관리 이력 저장은 가능합니다.`;
    }
    return `관리 기준 검토 범위는 ${SCOPE_NAME}입니다. 기준 사용 권한과 검토가 확정되지 않은 항목은 계산하지 않습니다.`;
  }

  return Object.freeze({ notice });
}));
