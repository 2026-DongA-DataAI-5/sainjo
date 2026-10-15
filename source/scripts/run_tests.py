"""저장소의 전체 Python 시험. --mysql은 준비된 전용 시험 DB도 검사합니다."""

import argparse
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql", action="store_true")
    args = parser.parse_args()
    if args.mysql:
        path = ROOT / ".mysql-test/runtime.json"
        if not path.exists():
            parser.error("전용 시험 DB의 로컬 설정이 없습니다. CI 또는 README의 시험 환경변수를 사용하세요.")
        local = json.loads(path.read_text(encoding="utf-8"))
        for field in ("host", "port", "user", "password"):
            os.environ["CHAGEUN_TEST_MYSQL_" + field.upper()] = str(local[field])
        os.environ["CHAGEUN_TEST_MYSQL_DATABASE"] = "chageun_test"
        os.environ["CHAGEUN_TEST_MYSQL_CONFIRM"] = "disposable-test-db"
    sys.path.insert(0, str(ROOT / "source"))
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(ROOT / "source/tests")))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
