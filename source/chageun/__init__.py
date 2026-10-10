import os

from flask import Flask, render_template


def _env_flag(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def create_app(test_config=None):
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config.update(
        # 서버 모드에서만 인증·DB 기능을 켭니다. 기본값은 꺼짐입니다.
        CHAGEUN_SERVER_MODE=_env_flag("CHAGEUN_SERVER_MODE"),
        SECRET_KEY=os.environ.get("CHAGEUN_SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # HTTPS 배포에서만 1로 설정합니다. 로컬 HTTP에서 켜면 로그인 쿠키가 저장되지 않습니다.
        SESSION_COOKIE_SECURE=_env_flag("CHAGEUN_COOKIE_SECURE"),
        MAX_CONTENT_LENGTH=64 * 1024,
        MYSQL_HOST=os.environ.get("CHAGEUN_MYSQL_HOST", "127.0.0.1"),
        MYSQL_PORT=int(os.environ.get("CHAGEUN_MYSQL_PORT", "3306")),
        MYSQL_USER=os.environ.get("CHAGEUN_MYSQL_USER", ""),
        MYSQL_PASSWORD=os.environ.get("CHAGEUN_MYSQL_PASSWORD", ""),
        MYSQL_DATABASE=os.environ.get("CHAGEUN_MYSQL_DATABASE", ""),
    )
    if test_config:
        app.config.update(test_config)

    from .routes import pages

    app.register_blueprint(pages)

    if app.config["CHAGEUN_SERVER_MODE"]:
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError("서버 모드에는 CHAGEUN_SECRET_KEY 환경변수가 필요합니다.")
        from .api import api
        from .repositories.db import init_app as init_db

        app.register_blueprint(api)
        init_db(app)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("not_found.html", title="화면을 찾을 수 없습니다"), 404

    @app.after_request
    def add_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        return response

    return app
