from flask import Flask, render_template


def create_app():
    app = Flask(__name__)
    app.json.ensure_ascii = False

    from .routes import pages

    app.register_blueprint(pages)

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
