import os

import pytest
from flask import Flask, session


class DummySociety:
    def __init__(self, sid: int):
        self.id = sid


class DummyUser:
    is_authenticated = True

    def __init__(self, primary_society_id: int, allowed: set[int] | None = None):
        self._primary = DummySociety(primary_society_id)
        self._allowed = allowed or {primary_society_id}

    def get_primary_society(self):
        return self._primary

    def can_access_society(self, society_id: int | None) -> bool:
        if not society_id:
            return True
        return int(society_id) in self._allowed


@pytest.fixture()
def mini_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    return app


def test_can_infers_scope_from_session(monkeypatch, mini_app):
    from app import utils as u

    captured = {}

    def fake_check_permission(user, resource, action, society_id=None):
        captured["user"] = user
        captured["resource"] = resource
        captured["action"] = action
        captured["society_id"] = society_id
        return True

    monkeypatch.setattr(u, "check_permission", fake_check_permission)

    user = DummyUser(primary_society_id=1, allowed={1, 99})
    with mini_app.test_request_context("/"):
        session["active_society_id"] = 99
        assert u.can("crm", "access", user=user) is True
        assert captured["society_id"] == 99


def test_can_falls_back_to_primary_society(monkeypatch, mini_app):
    from app import utils as u

    captured = {}

    def fake_check_permission(user, resource, action, society_id=None):
        captured["society_id"] = society_id
        return True

    monkeypatch.setattr(u, "check_permission", fake_check_permission)

    user = DummyUser(primary_society_id=7, allowed={7})
    with mini_app.test_request_context("/"):
        session["active_society_id"] = 999  # not accessible
        assert u.can("calendar", "view", user=user) is True
        assert captured["society_id"] == 7


def test_can_does_not_infer_scope_for_global_resources(monkeypatch, mini_app):
    from app import utils as u

    captured = {}

    def fake_check_permission(user, resource, action, society_id=None):
        captured["society_id"] = society_id
        return True

    monkeypatch.setattr(u, "check_permission", fake_check_permission)

    user = DummyUser(primary_society_id=7, allowed={7, 99})
    with mini_app.test_request_context("/"):
        session["active_society_id"] = 99
        assert u.can("admin", "access", user=user) is True
        assert captured["society_id"] is None

