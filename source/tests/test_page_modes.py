"""서버 화면에서 샘플·mock 자료가 실제 계정 자료로 표시되지 않게 검증합니다."""

import unittest
from chageun import create_app


class PageModeTests(unittest.TestCase):
    def test_live_pages_use_live_mode_and_do_not_show_sample_timelines(self):
        client = create_app({"TESTING": True, "CHAGEUN_SERVER_MODE": True, "SECRET_KEY": "page-test-only"}).test_client()
        for path in ("/vehicle", "/history/new", "/maintenance/new", "/timeline", "/dashboard", "/items/engine-oil", "/questions"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")
                text = response.get_data(as_text=True)
                self.assertTrue('data-api-mode="live"' in text, path)
                self.assertFalse("가상 저장(mock)" in text, path)
                self.assertFalse("75,000km" in text, path)
                self.assertFalse("화면 예시 · 날짜가 있는 기록" in text, path)
        dashboard = client.get("/dashboard").get_data(as_text=True)
        self.assertIn('data-management-controls hidden', dashboard)
        self.assertIn('data-management-content', dashboard)
        form = client.get("/maintenance/new").get_data(as_text=True)
        self.assertIn('value="unknown"', form)
        self.assertNotIn('value="coolant"', form)
        vehicle_form = client.get("/vehicle").get_data(as_text=True)
        self.assertIn("국내 판매 2021년형 기아 K5 DL3", vehicle_form)
        self.assertIn("다른 사양도 차량과 이력은 등록할 수 있지만", vehicle_form)
        self.assertIn("js/vehicle-scope.js", vehicle_form)
        detail = client.get("/items/engine-oil").get_data(as_text=True)
        self.assertIn('data-management-item="engine-oil"', detail)

    def test_mock_pages_and_assets_still_render(self):
        client = create_app({"TESTING": True}).test_client()
        for path in ("/", "/login", "/register", "/dashboard", "/vehicle", "/maintenance/new", "/timeline",
                     "/static/css/app.css", "/static/js/navigation.js"):
            with self.subTest(path=path):
                with client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
        self.assertIn('data-api-mode="mock"', client.get("/vehicle").get_data(as_text=True))
        dashboard = client.get("/dashboard").get_data(as_text=True)
        self.assertIn('data-management-controls ', dashboard)
        self.assertNotIn('data-management-controls hidden', dashboard)
