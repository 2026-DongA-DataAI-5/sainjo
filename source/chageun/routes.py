from flask import Blueprint, abort, current_app, jsonify, render_template, request

from .sample_data import DEMO_HISTORY, DEMO_ITEMS, DEMO_VEHICLE, STATUS_LABELS

pages = Blueprint("pages", __name__)


@pages.app_context_processor
def common_context():
    return {"vehicle": DEMO_VEHICLE, "status_labels": STATUS_LABELS}


@pages.get("/")
def home():
    return render_template("landing.html", title="중고차 구매 이후 관리")


def _auth_api_mode():
    # 서버 모드를 명시적으로 켰을 때만 실제 인증 API(live)를 사용합니다. 기본값은 mock입니다.
    return "live" if current_app.config.get("CHAGEUN_SERVER_MODE") else "mock"


@pages.get("/login")
def login():
    return render_template(
        "auth.html",
        title="로그인",
        auth_mode="login",
        api_mode=_auth_api_mode(),
        expired=request.args.get("expired") == "1",
    )


@pages.get("/register")
def register():
    return render_template("auth.html", title="회원가입", auth_mode="register", api_mode=_auth_api_mode(), expired=False)


@pages.get("/start")
def start():
    return render_template("start.html", title="차량 관리 시작하기")


@pages.get("/dashboard")
def dashboard():
    return render_template("dashboard.html", title="관리 대시보드", items=DEMO_ITEMS)


@pages.get("/vehicle")
def vehicle():
    return render_template("vehicle.html", title="차량 정보")


@pages.get("/history/new")
def history_new():
    return render_template("record_form.html", title="이전 관리이력 입력", is_result=False, items=DEMO_ITEMS)


@pages.get("/maintenance/new")
def maintenance_new():
    return render_template("record_form.html", title="정비 결과 입력", is_result=True, items=DEMO_ITEMS)


@pages.get("/items/<item_key>")
def item_detail(item_key):
    item = next((entry for entry in DEMO_ITEMS if entry["key"] == item_key), None)
    if item is None:
        abort(404)
    return render_template("item_detail.html", title=item["name"], item=item)


@pages.get("/questions")
def questions():
    items = [item for item in DEMO_ITEMS if any(label in item["labels"] for label in ("지금 확인할 항목", "이력 미확인"))]
    return render_template("questions.html", title="정비소 질문", items=items)


@pages.get("/timeline")
def timeline():
    return render_template("timeline.html", title="관리 타임라인", records=DEMO_HISTORY)


@pages.get("/api/health")
def health():
    return jsonify(status="ok", mode="prototype", persistence=False, authentication=False)


@pages.get("/api/demo/dashboard")
def demo_dashboard():
    return jsonify(mode="sample", vehicle=DEMO_VEHICLE, items=DEMO_ITEMS, persistence=False, calculation_connected=False)
