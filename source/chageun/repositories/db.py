"""MySQL 연결. 요청마다 연결을 열고 요청이 끝나면 닫습니다.

연결 정보는 환경변수(CHAGEUN_MYSQL_*)에서만 읽습니다. 비밀번호를 코드나 문서에 적지 않습니다.
"""

import pymysql
from flask import current_app, g


def get_db():
    if "db" not in g:
        config = current_app.config
        g.db = pymysql.connect(
            host=config["MYSQL_HOST"],
            port=config["MYSQL_PORT"],
            user=config["MYSQL_USER"],
            password=config["MYSQL_PASSWORD"],
            database=config["MYSQL_DATABASE"],
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
    return g.db


def _close_db(_error=None):
    # 커밋되지 않은 변경은 연결을 닫을 때 MySQL이 되돌립니다.
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(_close_db)
