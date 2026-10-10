# 관리 판단 서비스

`management.py`는 차량, 입력된 관리 기록, 적용 기준, 서버가 주입한 기준일을 받아 엔진 오일 교환 안내 1건을 반환합니다. 순수 Python 모듈이며 Flask, DB, HTML, 네트워크, 현재 시각에 의존하지 않습니다.

```python
from chageun.services.management import evaluate_management

item = evaluate_management(vehicle, records, rule, as_of_date="2026-06-01")
```

## 입력과 출력

- `vehicle`: 공통 기준의 차량 필드. `mileage=0`은 측정된 0km이고 `None`은 미확인입니다.
- `records`: `vehicle_id`, `item_key="engine-oil"`, `kind`, `work_type`, `date`, `mileage`를 가진 사용자 입력 기록입니다.
- `rule`: 기준 사양, 운행조건, 거리·개월 주기, 출처, 확인일, 권한·검토 상태를 포함합니다. 실제 기준은 `rights_status="allowed"`, `review_status="reviewed"`, `is_fixture=False`인 경우에만 계산에 사용합니다. 시험 fixture는 `rights_status="test_fixture"`, `review_status="reviewed"`, `is_fixture=True`여야 합니다.
- `as_of_date`: `YYYY-MM-DD` 형식의 평가 기준일. 서버 또는 호출자가 주입합니다.
- 반환 dict는 공통 v1.0 필드(`item_key`, `history_status`, `timing_status`, `labels`, `next_mileage`, `next_date`, `reasons`, `missing_fields`, `rule_id`, `source`, `checked_date`, `questions`, `is_fixture`)를 가집니다.

`timing_status`는 `due`, `upcoming`, `partial`, `unknown`, `unsupported` 중 하나입니다. 도달 여부는 거리·기간 축별로 계산합니다. 계산 가능한 축이 하나라도 도달하면 `due`, 필요한 모든 축이 확인되어 미도달이면 `upcoming`, 일부 축만 계산되면 `partial`입니다. 계산 근거가 없으면 `unknown`, 사양이나 항목이 적용 범위 밖이면 `unsupported`입니다.

## 안전한 계산 원칙

- 지원 대상 사양은 제공된 fixture의 정확한 문자열과 K5 DL3 2.0 가솔린 G2.0 CVVL 2020~2023년식입니다. 사양을 부분 일치시키지 않습니다.
- 운행조건은 기준과 차량 양쪽이 확인되고 일치해야 합니다. `unknown` 조건으로 주기를 확정하지 않습니다.
- 자료 없음은 미정비를 뜻하지 않습니다. 기록이 없거나 작업유형이 `unknown`뿐이면 이력 상태도 `unknown`입니다.
- 점검 기록은 이력으로만 남고 교환 기준을 갱신하지 않습니다. `replacement` 기록만 일정을 계산합니다.
- 날짜가 없는 교환을 `created_at`으로 정렬하거나 정비일로 간주하지 않습니다. 여러 교환의 순서를 정할 수 없거나 날짜·주행거리가 충돌하면 계산을 보류합니다.
- 현재 주행거리는 `reference_date == as_of_date`일 때만 거리 기준에 사용합니다. 오래된 측정, 누락값, 주행거리 역전은 해당 축을 미확인으로 둡니다.
- 월 계산은 달력 기준이며 대상 월 말일에 맞춰 일자를 조정합니다. 경계값은 도달로 봅니다.
- 실제 주기나 교환 필요를 단정하지 않습니다. fixture 결과에는 `is_fixture=True`가 유지됩니다.

## 적용 제외

이 구현은 엔진 오일 교환 일정 한 항목의 계산만 담당합니다. 최초 교환 주기, 다단계·복합 작업, 차량 고장 진단, 제조사 자료 수집·권리 검토, 증빙 자동 검증, API·DB·화면 연결은 범위에 포함하지 않습니다. 제공된 수치와 테스트는 실제 기아 권장 주기가 아닙니다.

## 고정 fixture와 테스트

`tests/fixtures/management.json`은 팀에서 전달한 v1.0 입력·예상값을 변경 없이 보존합니다. 추가 경계·누락·충돌 사례는 `tests/test_management.py`의 표 기반 테스트로 관리합니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_management*.py"
```
