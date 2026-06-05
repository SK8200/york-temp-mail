import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
MODULE_NAME = "mail_viewer_app_under_test"


def load_app(monkeypatch, **env):
    defaults = {
        "ENVIRONMENT": "development",
        "SECRET_KEY": "test-secret-key",
        "ACCESS_PASSWORD": "viewer-pass",
        "DUCKMAIL_API_KEY": "test-api-key",
        "UNIFIED_PASSWORD": "mailbox-pass",
        "DUCKMAIL_BASE_URL": "http://mail-service.test",
        "IMAP_MAIL_BASE_URL": "http://imap-mail.test",
        "AUTO_CREATE_ACCOUNTS": "0",
        "RESEND_API_KEY": "",
        "LOGIN_RATE_LIMIT_MAX": "2",
        "LOGIN_RATE_LIMIT_WINDOW": "300",
        "SENSITIVE_RATE_LIMIT_MAX": "2",
        "SENSITIVE_RATE_LIMIT_WINDOW": "60",
    }
    defaults.update(env)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)

    sys.modules.pop(MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(MODULE_NAME, APP_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True)
    return module


@pytest.fixture
def viewer(monkeypatch):
    module = load_app(monkeypatch)
    return module


@pytest.fixture
def client(viewer):
    with viewer.app.test_client() as test_client:
        yield test_client


def login(test_client):
    return test_client.post("/login", data={"password": "viewer-pass"})


def test_login_required_blocks_json(client):
    resp = client.post("/api/inbox/query", json={"email": "user@test.local"})
    assert resp.status_code == 401
    assert resp.get_json()["message"] == "未授权访问"


def test_login_uses_rate_limit(client):
    assert client.post("/login", data={"password": "bad"}).status_code == 200
    assert client.post("/login", data={"password": "bad"}).status_code == 200
    resp = client.post("/login", data={"password": "bad"})
    assert resp.status_code == 429


def test_image_proxy_rejects_private_address(client, viewer, monkeypatch):
    login(client)
    monkeypatch.setattr(viewer.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 0))])
    resp = client.get("/api/image-proxy?url=http://internal.local/image.png")
    assert resp.status_code == 400


def test_sanitize_email_html_removes_script(viewer):
    html = viewer._sanitize_email_html('<div onclick="alert(1)"><script>alert(1)</script><b>ok</b></div>')
    assert "script" not in html.lower()
    assert "onclick" not in html.lower()
    assert "<b>ok</b>" in html


def test_inbox_query_does_not_auto_create_when_disabled(client, viewer, monkeypatch):
    login(client)
    post = Mock(return_value=Mock(status_code=401))
    monkeypatch.setattr(viewer.http_session, "post", post)

    resp = client.post("/api/inbox/query", json={"email": "new@test.local"})

    assert resp.status_code == 200
    assert resp.get_json()["success"] is False
    assert "自动创建已关闭" in resp.get_json()["message"]
    assert post.call_count == 1


def test_inbox_query_auto_create_enabled(monkeypatch):
    module = load_app(monkeypatch, AUTO_CREATE_ACCOUNTS="1")
    module.app.config.update(TESTING=True)
    with module.app.test_client() as test_client:
        login(test_client)
        token_resp_1 = Mock(status_code=401)
        create_resp = Mock(status_code=201)
        token_resp_2 = Mock(status_code=200)
        token_resp_2.json.return_value = {"token": "token-1"}
        module.http_session.post = Mock(side_effect=[token_resp_1, create_resp, token_resp_2])
        mail_resp = Mock(status_code=200)
        mail_resp.json.return_value = {"hydra:member": [], "hydra:totalItems": 0}
        module.http_session.get = Mock(return_value=mail_resp)

        resp = test_client.post("/api/inbox/query", json={"email": "new@test.local"})

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert module.http_session.post.call_count == 3


def test_send_requires_resend_key(client):
    login(client)
    resp = client.post("/api/send", json={})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False
    assert "Resend" in resp.get_json()["message"]


def test_domain_proxy_masks_internal_exception(client, viewer, monkeypatch):
    login(client)
    monkeypatch.setattr(viewer.http_session, "get", Mock(side_effect=RuntimeError("boom secret")))

    resp = client.get("/api/domains")

    assert resp.status_code == 502
    assert resp.get_json()["message"] == "获取域名失败"
