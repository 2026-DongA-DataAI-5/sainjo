"""로컬 실행. --mock은 정적 미리보기, 기본은 준비된 전용 시험 DB를 사용합니다."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "source"))

from chageun import create_app


def main():
    parser = argparse.ArgumentParser(description="차근 로컬 개발 서버")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--fixture", action="store_true", help="실제 제조사 기준이 아닌 가상 시험 기준을 명시적으로 사용")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    config = {"CHAGEUN_SERVER_MODE": not args.mock, "CHAGEUN_ALLOW_TEST_FIXTURE": args.fixture}
    if not args.mock:
        path = ROOT / ".mysql-test/runtime.json"
        if not path.is_file():
            parser.error("전용 시험 DB의 로컬 설정이 없습니다. README의 환경변수 실행 방법을 사용하세요.")
        local = json.loads(path.read_text(encoding="utf-8"))
        config.update(SECRET_KEY=local["secret_key"], **{
            "MYSQL_" + key.upper(): local[key] for key in ("host", "port", "user", "password", "database")
        })
    create_app(config).run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
