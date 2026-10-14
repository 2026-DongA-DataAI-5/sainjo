# 차근 | 중고차 구매 이후 관리

차근은 사용자가 입력한 차량 정보와 관리 이력을 모아 확인할 항목을 안내합니다. 실제 고장을 진단하지 않습니다.

## 현재 연결 범위

- 회원가입·로그인·로그아웃과 세션·CSRF 인증
- 계정당 차량 1대 등록·목록·상세 조회, 주행거리·측정 기준일 수정
- 엔진오일 기록 저장·목록·수정·삭제 API와 타임라인 연결: 점검 / 교환 / 작업유형 미확인, CSRF·계정 소유권 확인, 삭제 전 확인
- 실제 DB 기록을 순수 Python 관리판단 엔진에 전달하고 화면에 결과 표시
- 로그인부터 차량·기록 저장, 재로그인 후 재조회, 다른 계정 접근 차단

실제 제조사 관리기준과 자료 이용 허락은 미확정입니다. 기본 관리 조회는 `calculation_mode=unavailable`이며 주기를 확정하지 않습니다. 개발자가 명시적으로 켠 가상 기준은 `test_fixture`, `is_fixture=true`로 표시하며 실제 기아 권장 주기가 아닙니다. 적용 대상은 K5 DL3 2.0 가솔린 G2.0 CVVL 2020~2023이고 JF·다른 사양에 자동 적용하지 않습니다.

차량 기본정보 수정(제조사·모델·연식 등), OCR, 외부 자동 조회, 운영 서버 배포는 남은 작업입니다. 사용자 입력의 출처·확인일은 증빙 자동 검증 결과가 아닙니다. 기록 없음은 미정비나 고장을 뜻하지 않으며 점검은 교환 기준을 초기화하지 않습니다.

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

가상 기준 계산을 시험하려면 `--fixture`를 명시합니다. 기본 실행은 실제 주기를 계산하지 않습니다. DB 없이 가상 미리보기만 실행하려면 `--mock`을 사용합니다.

```powershell
.\.venv\Scripts\python.exe source/scripts/run_local.py --fixture
.\.venv\Scripts\python.exe source/scripts/run_local.py --mock --port 8082
```

다른 MySQL 환경은 `CHAGEUN_SERVER_MODE=1`, `CHAGEUN_SECRET_KEY`, `CHAGEUN_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` 환경변수를 로컬에서 설정하고 `source/app.py`를 실행합니다. `.env`를 자동으로 읽는 기능은 없습니다. HTTPS 운영 배포에서는 `CHAGEUN_COOKIE_SECURE=1`도 필요하며 현재 개발 서버는 운영용 서버가 아닙니다.

## 검증

기본 전체 시험은 실제 MySQL 시험 5개를 건너뜁니다. `--mysql`은 준비된 전용 시험 DB에 연결합니다. 기존 가드가 DB 이름, 연결 DB, 테이블, 비어 있는 users를 확인하므로 사용자 DB를 비우거나 우회하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -B source/scripts/run_tests.py
.\.venv\Scripts\python.exe -B source/scripts/run_tests.py --mysql
.\.venv\Scripts\python.exe -B source/scripts/build_pages.py
```

GitHub의 Python/MySQL workflow는 버려지는 MySQL 8.0 서비스에서 스키마를 만들고 전체 시험과 정적 빌드를 실행합니다. workflow의 암호는 해당 임시 CI 서비스에만 쓰는 고정 시험값이며 운영 자격증명이 아닙니다.

브라우저 시험은 별도로 Node.js와 Playwright가 준비된 환경에서 서버를 실행한 뒤 `node source/tests/browser-flow.cjs`로 수행합니다. 설치된 Chrome을 사용할 때는 `CHAGEUN_BROWSER_EXECUTABLE`, 다른 서버 주소는 `CHAGEUN_BROWSER_BASE`를 지정합니다. 화면 증거는 Git에서 제외된 `.mysql-test/screenshots/`에 저장됩니다.

## 정적 미리보기

[GitHub Pages](https://2026-donga-dataai-5.github.io/sainjo/)는 main의 mock 정적 미리보기입니다. Flask·MySQL 서버를 실행하지 않으므로 실제 가입·로그인·DB 저장을 제공하지 않습니다. 작업 브랜치의 구현은 main 병합과 배포 전까지 공개 미리보기에 반영되지 않습니다.
