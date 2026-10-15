"""계정별 질문 선택의 인증·CSRF·검증·멱등성을 확인합니다."""

import unittest
from unittest import mock

from chageun import create_app


class QuestionSelectionApiTests(unittest.TestCase):
    def setUp(self):
        self.keys = set()
        self.db = mock.MagicMock()
        self.patchers = [
            mock.patch('chageun.api.vehicles.find_vehicle_by_id_and_owner',
                       side_effect=lambda vehicle, owner: {'id': 1} if (vehicle, owner) == (1, 1) else None),
            mock.patch('chageun.api.get_db', return_value=self.db),
            mock.patch('chageun.api.question_selections.list_keys', side_effect=lambda vehicle: sorted(self.keys)),
            mock.patch('chageun.api.question_selections.set_selected', side_effect=self.set_selected),
            mock.patch('chageun.api.question_selections.clear', side_effect=lambda vehicle: self.keys.clear()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = create_app({'TESTING': True, 'CHAGEUN_SERVER_MODE': True, 'SECRET_KEY': 'questions-test-only'})
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = 1
        self.path = '/api/vehicles/1/question-selections'
        self.body = {'question_key': 'a' * 64, 'selected': True}

    def set_selected(self, vehicle, key, selected):
        if selected and key not in self.keys and len(self.keys) >= 200:
            return False
        self.keys.add(key) if selected else self.keys.discard(key)
        return True

    def write(self, client=None, body=None, method='patch', path=None, csrf=True):
        client = client or self.client
        headers = {}
        if csrf:
            headers['X-CSRF-Token'] = client.get('/api/auth/csrf').get_json()['data']['csrf_token']
        return getattr(client, method)(path or self.path, json=self.body if body is None else body, headers=headers)

    def test_selection_is_idempotent_and_can_be_removed(self):
        for _ in range(2):
            self.assertEqual(self.write().status_code, 200)
        self.assertEqual(self.client.get(self.path).get_json()['data']['selected_question_keys'], ['a' * 64])
        self.assertEqual(self.write(body={**self.body, 'selected': False}).status_code, 200)
        self.assertEqual(self.client.get(self.path).get_json()['data']['selected_question_keys'], [])

    def test_anonymous_requests_are_401_before_csrf(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get(self.path).status_code, 401)
        for method in ('patch', 'delete'):
            self.assertEqual(self.write(anonymous, method=method, csrf=False).status_code, 401)

    def test_writes_require_csrf(self):
        for method in ('patch', 'delete'):
            self.assertEqual(self.write(method=method, csrf=False).status_code, 403)
        self.assertEqual(self.keys, set())

    def test_other_account_and_missing_vehicle_are_same_404(self):
        other = self.app.test_client()
        with other.session_transaction() as session:
            session['user_id'] = 2
        for method in ('patch', 'delete'):
            actual = self.write(other, method=method)
            missing = self.write(other, method=method, path='/api/vehicles/999/question-selections')
            self.assertEqual(actual.status_code, 404)
            self.assertEqual(actual.get_json(), missing.get_json())
        self.assertEqual(other.get(self.path).status_code, 404)
        self.assertEqual(self.keys, set())

    def test_invalid_inputs_cannot_change_selection(self):
        cases = [[], {}, {'question_key': 'a', 'selected': True},
                 {**self.body, 'selected': 1}, {**self.body, 'selected': 'true'},
                 {**self.body, 'question_key': []}, {**self.body, 'owner_id': 2}]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.write(body=body).status_code, 400)
                self.assertEqual(self.keys, set())

    def test_selection_limit_preserves_existing_choices_and_allows_clear(self):
        self.keys = {f'{number:064x}' for number in range(200)}
        self.assertEqual(self.write().status_code, 409)
        self.assertEqual(len(self.keys), 200)
        self.db.rollback.assert_called()
        self.assertEqual(self.write(body={'question_key': f'{0:064x}', 'selected': True}).status_code, 200)
        self.assertEqual(self.write(method='delete').status_code, 200)
        self.assertEqual(self.keys, set())
