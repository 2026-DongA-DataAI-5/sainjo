"""진입점: 화면과 읽기 전용 샘플 API를 실행합니다."""

from chageun import create_app

app = create_app()

if __name__ == "__main__":
    # 개발 초안은 이 컴퓨터에서만 접근합니다.
    app.run(host="127.0.0.1", port=8081, debug=False)
