"""Windows의 설치된 MySQL로 이 저장소 전용 시험 서버를 준비합니다. 기존 서비스는 변경하지 않습니다."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time

import pymysql

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".mysql-test"
DATA = LOCAL / "data"
CONFIG = LOCAL / "runtime.json"


def executable():
    found = shutil.which("mysqld")
    candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "MySQL/MySQL Server 8.0/bin/mysqld.exe"
    if found:
        return found
    if candidate.is_file():
        return str(candidate)
    raise RuntimeError("MySQL 8.0 실행 파일이 없습니다. 설치된 MySQL 경로를 PATH에 추가해 주세요.")


def port_open(port):
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def connection(config, bootstrap=False):
    conn = pymysql.connect(host="127.0.0.1", port=config["port"], user="root",
                           password="" if bootstrap else config["root_password"], autocommit=True,
                           connect_timeout=2)
    with conn.cursor() as cursor:
        cursor.execute("SELECT @@datadir")
        actual = Path(cursor.fetchone()[0]).resolve()
        if str(actual).casefold() != str(DATA.resolve()).casefold():
            conn.close()
            raise RuntimeError("이 저장소 전용 데이터 폴더가 아니므로 작업을 중단합니다.")
    return conn


def launch(config):
    if port_open(config["port"]):
        with connection(config):
            pass
        print("전용 시험 MySQL이 이미 실행 중입니다.")
        return
    LOCAL.mkdir(exist_ok=True)
    with (LOCAL / "mysql.log").open("ab") as log:
        process = subprocess.Popen([executable(), "--no-defaults", f"--datadir={DATA}",
                                    f"--port={config['port']}", "--bind-address=127.0.0.1", "--mysqlx=0",
                                    "--lower-case-table-names=1", "--innodb-buffer-pool-size=64M", "--console"],
                                   stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("시험 서버가 종료됐습니다. .mysql-test/mysql.log를 확인해 주세요.")
        if port_open(config["port"]):
            return process
        time.sleep(0.1)
    raise RuntimeError("시험 서버 시작 시간이 초과됐습니다. .mysql-test/mysql.log를 확인해 주세요.")


def initialize(port):
    if DATA.exists() or CONFIG.exists():
        raise RuntimeError("로컬 데이터 또는 설정이 이미 있습니다. 초기화하지 않고 start를 사용하세요.")
    if port_open(port):
        raise RuntimeError("선택한 포트가 사용 중입니다. --port로 다른 시험 포트를 지정해 주세요.")
    DATA.mkdir(parents=True)
    with (LOCAL / "mysql.log").open("ab") as log:
        subprocess.run([executable(), "--no-defaults", "--initialize-insecure", f"--datadir={DATA}",
                        "--lower-case-table-names=1", "--innodb-buffer-pool-size=64M"],
                       stdout=log, stderr=log, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    config = {"host": "127.0.0.1", "port": port, "user": "chageun_local", "database": "chageun_test_demo",
              "password": secrets.token_urlsafe(32), "root_password": secrets.token_urlsafe(32),
              "secret_key": secrets.token_urlsafe(48)}
    process = launch(config)
    try:
        with connection(config, bootstrap=True) as conn:
            with conn.cursor() as cursor:
                cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (config["root_password"],))
                cursor.execute("CREATE USER 'chageun_local'@'localhost' IDENTIFIED BY %s", (config["password"],))
                schema = "\n".join(line for line in (ROOT / "source/chageun/schema.sql").read_text(encoding="utf-8").splitlines()
                                   if not line.lstrip().startswith("--"))
                for database in ("chageun_test", "chageun_test_demo"):
                    cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4")
                    cursor.execute(f"USE `{database}`")
                    for statement in schema.split(";"):
                        if statement.strip():
                            cursor.execute(statement)
                    cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{database}`.* TO 'chageun_local'@'localhost'")
        CONFIG.write_text(json.dumps(config), encoding="utf-8")
    except Exception:
        if process is not None:
            process.terminate()
        raise
    print("전용 시험 DB 두 개를 준비했습니다. 접속 정보는 Git에서 제외된 로컬 설정에만 저장했습니다.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "start", "stop", "status"))
    parser.add_argument("--port", type=int, default=3308)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("시험 포트는 1024~65535 사이여야 합니다.")
    try:
        if args.action == "init":
            initialize(args.port)
            return
        if not CONFIG.is_file():
            raise RuntimeError("로컬 설정이 없습니다. 최초 한 번 init을 실행하세요.")
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        if args.action == "start":
            launch(config)
        elif not port_open(config["port"]):
            print("전용 시험 MySQL이 중지돼 있습니다.")
        else:
            with connection(config) as conn:
                with conn.cursor() as cursor:
                    if args.action == "stop":
                        cursor.execute("SHUTDOWN")
                        print("이 저장소 전용 시험 MySQL을 중지했습니다.")
                    else:
                        cursor.execute("SELECT VERSION()")
                        print("전용 시험 MySQL:", cursor.fetchone()[0], "포트:", config["port"])
    except (RuntimeError, pymysql.MySQLError, subprocess.CalledProcessError) as error:
        # DB 연결 오류에는 서버 정보가 포함될 수 있어 실제 세부 내용은 출력하지 않습니다.
        parser.exit(1, (str(error) if isinstance(error, RuntimeError) else "시험 DB 작업 실패. 로컬 로그를 확인해 주세요.") + "\n")


if __name__ == "__main__":
    main()
