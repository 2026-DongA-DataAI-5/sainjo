# 차근 | 중고차 구매 이후 관리

차근은 사용자가 입력한 차량 정보와 관리 이력을 모아 확인할 항목을 안내합니다. 실제 고장을 진단하지 않습니다.

## 현재 연결 범위

- 회원가입·로그인·로그아웃과 세션·CSRF 인증
- 계정당 차량 1대 등록·목록·상세 조회·부분 수정
- 관리기록 저장·목록·수정·삭제 API와 타임라인 연결: 점검 / 교환 / 작업유형 미확인, CSRF·계정 소유권 확인, 삭제 전 확인
- 실제 DB 기록을 순수 Python 관리판단 엔진에 전달하고 화면에 결과 표시
- 로그인부터 차량·기록 저장, 재로그인 후 재조회, 다른 계정 접근 차단

기아 공식 취급설명서에서 국내 K5 DL3 2021년형 G2.0 CVVL의 정비 후보 기준을 확인해 프로토타입 계산에 연결했습니다. 결과에는 **사용 권리 확인 중**을 표시하며, 기아가 차근의 계산·안내를 승인한 상태가 아닙니다. 적용 범위는 2021년형 한정이며 2020·2022·2023년형, JF, 다른 엔진·연료·변속기에 확대 적용하지 않습니다. 별도로 켠 가상 시험 기준은 `test_fixture`, `is_fixture=true`로 표시하며 실제 기아 권장 주기가 아닙니다. 자세한 상태와 근거는 [`SOURCE_RIGHTS_REVIEW.md`](source/chageun/services/SOURCE_RIGHTS_REVIEW.md)를 참고하세요.

사용자 입력의 출처·확인일은 증빙 자동 검증 결과가 아닙니다. 기록 없음은 미정비나 고장을 뜻하지 않으며 점검은 교환 기준을 초기화하지 않습니다.

## 발표 목표와 추가 개발 범위 (2026-10-14 확정)

- 기준 차량은 국내 판매 **2021년형 기아 K5 3세대 DL3, 2.0 가솔린, 스마트스트림 G2.0 CVVL, 자동변속기** 한 사양으로 고정합니다. 연식은 최초 등록연도가 아닌 모델 연식입니다.
- 차량 한 대의 현재 주행거리, 운행조건, 관리 이력을 받아 소모품과 경정비의 다음 행동을 자동 안내합니다. 사용자가 교환 주기를 직접 정하는 것을 핵심 기능으로 삼지 않습니다.
- 엔진오일·오일필터는 통상조건 매 15,000 km 또는 12개월, 선택한 가혹조건 1~12번은 매 7,500 km 또는 6개월 후보 기준을 관리 이력부터 계산합니다. 해당 가혹조건 번호를 선택하지 않으면 가혹 주기를 적용하지 않습니다. 그 밖에 **엔진 에어클리너 필터, 점화플러그, 구동벨트, 브레이크액, 공조 필터, 냉각수, 브레이크 패드·디스크, 로워암, 볼 조인트 관련 점검 및 정비 이력**을 개발 범위에 추가합니다. 점화플러그는 통상조건에서 165,000 km 교환 기준을 적용하고, 가혹조건 1·3·7·9번은 상태 점검으로 안내합니다. 엔진 에어클리너는 통상조건 10,000 km 점검과 40,000 km 교환을 각각 계산하고, 가혹조건 2·5번은 상태 점검으로 안내합니다. 사용자가 선택한 세부 운행조건 번호가 해당 부품에 맞을 때만 가혹조건 기준을 적용합니다. 냉각수는 통상조건에서 첫 200,000 km 또는 10년, 이후 40,000 km 또는 24개월 기준과 교환 기록을 비교합니다. 최초 등록일이 없으면 시간축은 미확인으로 둡니다. 별도 수치 주기가 확인되지 않거나 필요한 운행조건이 확인되지 않으면 정비소에서 상태·이력을 확인하도록 합니다. 로워암과 볼 조인트는 별도 항목으로 입력하고 이력을 분리합니다. 로워암은 현재 이력 기록만 지원하며 교환 주기나 진단을 제공하지 않습니다. 권리 확인 상태와 현재 지원 항목은 [`관리 판단 서비스`](source/chageun/services/README.md)를 참고하세요.
- 정기 교환, 정기 점검, 상태에 따른 정비를 구분하고, 결과마다 적용 근거와 정비소 질문을 제공합니다. 실제 고장이나 부품의 정상 상태를 확정하지 않습니다.
- 발표는 등록 → 관리 안내 → 정비소 질문 → 교환 또는 점검 기록 저장 → 안내 갱신 순서로 구성합니다. 최근 교환은 확인된 이력으로 표시하고, 점검만 한 경우 교환 완료로 바꾸지 않습니다.
- 세부 판단 및 검증 사례는 [관리 판단 서비스의 경정비 확장 범위와 현재 상태](source/chageun/services/README.md#경정비-확장-요구사항-및-현재-상태)를 따릅니다.
- 11월 초 시연 준비를 위해 위 흐름을 우선 완성합니다. OCR, 외부 차량이력 자동 조회, 운영 서버 배포는 이번 핵심 흐름의 필수 선행조건으로 두지 않습니다.

## 소스 기준과 실행 환경

실행·시험·Pages 빌드의 기준은 Git으로 추적하는 `source/`입니다. `sainjo-source.zip`은 이전 미리보기 보관본이며 현재 개발 소스 위에 풀지 않습니다. Pages workflow도 ZIP을 풀지 않습니다.

Windows, Python 3.12, Flask/Jinja, 기존 JavaScript/CSS, MySQL 8.0을 기준으로 합니다. 최초 환경 준비는 저장소 루트에서 실행합니다. Python 3.12가 설치돼 있어야 합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r source/requirements-lock.txt
```

## 전용 로컬 시험 DB

MySQL 8.0 실행 파일이 설치된 Windows에서 최초 한 번 아래를 실행합니다. 기존 MySQL 서비스와 사용자 DB는 변경하지 않습니다. 기본 포트는 3308이며 사용 중이면 `--port 3310`처럼 별도 포트를 선택합니다.

```powershell
.\.venv\Scripts\python.exe source/scripts/local_mysql.py init
```

시험용 `chageun_test`와 화면 확인용 `chageun_test_demo`를 별도 데이터 폴더에 만들고, 앱 계정에는 두 DB의 SELECT/INSERT/UPDATE/DELETE만 부여합니다. 초기화 직후 임시 관리자 암호를 설정합니다. 비밀번호·세션 키는 Git에서 제외되는 `.mysql-test/runtime.json`에만 보관하며 공유하지 않습니다.

이미 준비된 PC에서는 초기화 대신 시작·상태·중지를 사용합니다. 중지는 이 저장소의 데이터 폴더를 확인한 서버에만 적용하며 데이터를 삭제하지 않습니다.

```powershell
.\.venv\Scripts\python.exe source/scripts/local_mysql.py start
.\.venv\Scripts\python.exe source/scripts/local_mysql.py status
.\.venv\Scripts\python.exe source/scripts/local_mysql.py stop
```

## 서버 화면 확인

시험 MySQL이 실행 중일 때 다음을 실행하고 `http://127.0.0.1:8081/register`에서 직접 계정을 만듭니다. 가입 후 로그인하고 차량을 등록합니다.

```powershell
.\.venv\Scripts\python.exe source/scripts/run_local.py
```

실제 프로토타입 규칙 계산은 권리 확인 중 상태를 화면에 표시합니다. 계산기 시험용 가상 기준을 별도로 사용하려면 `--fixture`를 명시합니다. DB 없이 가상 미리보기만 실행하려면 `--mock`을 사용합니다.

```powershell
.\.venv\Scripts\python.exe source/scripts/run_local.py --fixture
.\.venv\Scripts\python.exe source/scripts/run_local.py --mock --port 8082
```

다른 MySQL 환경은 `CHAGEUN_SERVER_MODE=1`, `CHAGEUN_SECRET_KEY`, `CHAGEUN_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` 환경변수를 로컬에서 설정하고 `source/app.py`를 실행합니다. `.env`를 자동으로 읽는 기능은 없습니다. HTTPS 운영 배포에서는 `CHAGEUN_COOKIE_SECURE=1`도 필요하며 현재 개발 서버는 운영용 서버가 아닙니다.

## 검증

기본 전체 시험은 실제 MySQL 시험 9개를 건너뜁니다. `--mysql`은 준비된 전용 시험 DB에 연결합니다. 기존 가드가 DB 이름, 연결 DB, 테이블, 비어 있는 users를 확인하므로 사용자 DB를 비우거나 우회하지 않습니다. 기존 시험 DB에 자료가 있으면 새 전용 DB를 준비하거나 GitHub Actions의 임시 MySQL에서 검증합니다.

```powershell
.\.venv\Scripts\python.exe -B source/scripts/run_tests.py
.\.venv\Scripts\python.exe -B source/scripts/run_tests.py --mysql
.\.venv\Scripts\python.exe -B source/scripts/build_pages.py
```

GitHub Actions는 버려지는 MySQL 8.0 서비스에서 Python·DB 시험을 마친 뒤, 별도 임시 DB에서 Playwright Chromium 브라우저 흐름도 실행합니다. 브라우저 시험 실패 시 화면 자료와 서버 로그를 workflow artifact로 보관합니다. CI 암호는 해당 임시 시험 서비스에만 쓰며 운영 자격증명이 아닙니다.

브라우저 시험은 Node.js가 설치된 PC에서 아래 순서로 실행합니다. 첫 설치 때 Playwright 의존성을 복원하고 Playwright와 맞는 Chromium을 받습니다. 이후에는 MySQL과 앱을 켠 뒤 브라우저 시험 명령을 실행하면 됩니다. 앱은 `127.0.0.1:8081`에서 실행해야 하며, 별도 주소를 쓸 때는 `CHAGEUN_BROWSER_BASE`를 지정합니다. 화면 증거는 Git에서 제외된 `.mysql-test/screenshots/`에 저장됩니다.

```powershell
# 저장소 루트: 시험용 MySQL 시작
.\.venv\Scripts\python.exe source/scripts/local_mysql.py start

# source/tests 폴더에서 최초 한 번: Playwright와 Chromium 설치
Set-Location source\tests
npm ci
npx playwright install chromium

# 별도 터미널에서 저장소 루트 기준: 실제 서버 화면 실행
Set-Location ..\..
.\.venv\Scripts\python.exe source/scripts/run_local.py

# source/tests 폴더에서: 실제 가입·차량·기록·재로그인 브라우저 시험
Set-Location source\tests
npm run test:browser
```

브라우저 시험은 별도의 실제 DB 저장 계정을 사용합니다. MySQL 시험용 Python 테스트와 같은 DB를 쓰지 않으며, 테스트 계정·차량·기록이 `chageun_test_demo`에 남을 수 있습니다. 설치된 Chrome을 쓰려면 `CHAGEUN_BROWSER_EXECUTABLE`을 지정합니다.

## 정적 미리보기

[GitHub Pages](https://2026-donga-dataai-5.github.io/sainjo/)는 main의 mock 정적 미리보기입니다. Flask·MySQL 서버를 실행하지 않으므로 실제 가입·로그인·DB 저장을 제공하지 않습니다. 작업 브랜치의 구현은 main 병합과 배포 전까지 공개 미리보기에 반영되지 않습니다.
