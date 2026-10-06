# 차근 | 중고차 구매 이후 관리

차근은 차량 기본 정보와 사용자가 기록한 관리 이력·정비 결과를 한곳에 모아 다음에 확인할 항목을 살펴보도록 돕는 웹 프로젝트입니다. 실제 고장을 진단하지 않으며, 화면의 관리 항목은 가상 예시입니다.

## 사이트

https://2026-donga-dataai-5.github.io/sainjo/

## 현재 구현 범위

- 차량 정보와 사용자가 입력한 이전 이력·정비 결과를 이 브라우저에 저장하고 다시 표시합니다.
- 정비소 방문 질문 체크와 타임라인 JSON 내보내기를 지원합니다.
- 로그인, 서버 데이터베이스, OCR, 외부 API·자동 조회, 차종별 관리주기 자동 계산은 구현되지 않았습니다.
- 입력 이력의 출처는 입력자가 고른 값이며, 문서와 자동 대조하지 않습니다.

## 소스와 실행

프로젝트 소스는 폴더 구조를 보존한 `sainjo-source.zip`에 있습니다. 압축을 풀고 프로젝트 폴더에서 아래 명령으로 실행합니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe app.py
```

기본 주소는 `http://127.0.0.1:8081`입니다. GitHub Actions는 소스 압축을 풀어 정적 페이지를 빌드한 뒤 GitHub Pages에 배포합니다.
