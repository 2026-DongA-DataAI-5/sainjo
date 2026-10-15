const assert = require('node:assert/strict');
const test = require('node:test');
const { notice } = require('../chageun/static/js/vehicle-scope.js');

const supportedVehicle = {
  manufacturer: '기아',
  model: 'K5',
  generation: 'DL3',
  year: 2021,
  engine: 'G2.0 CVVL',
  fuel: '가솔린',
  transmission: '자동',
};

test('supported vehicle shows the exact scope and pending approval boundary', () => {
  const message = notice(supportedVehicle);
  assert.match(message, /2021년형 기아 K5 DL3/);
  assert.match(message, /기준 사용 권한과 검토가 확정되지 않은 항목은 계산하지 않습니다/);
});

test('a different model year is explicitly kept outside the K5 criteria', () => {
  const message = notice({ ...supportedVehicle, year: 2022 });
  assert.match(message, /현재 차량 사양은 범위 밖이라 이 기준을 적용하지 않습니다/);
  assert.match(message, /차량 등록과 관리 이력 저장은 가능합니다/);
});

test('missing identity fields are reported as unconfirmed rather than out of scope', () => {
  const vehicle = { ...supportedVehicle };
  delete vehicle.engine;
  const message = notice(vehicle);
  assert.match(message, /엔진 정보가 없어 적용 여부를 확인할 수 없습니다/);
  assert.doesNotMatch(message, /범위 밖/);
});

test('null vehicle data is reported as unconfirmed', () => {
  assert.match(notice(null), /제조사·모델·세대·연식·엔진·연료·변속기 정보가 없어 적용 여부를 확인할 수 없습니다/);
});
