from unittest.mock import MagicMock, patch

from webuntis_mcp.auth import totp_login


def _login(user_data):
    resp = MagicMock()
    resp.headers = {"Set-Cookie": "JSESSIONID=abc; Path=/"}
    resp.json.return_value = {"result": {"userData": user_data}}
    with patch("webuntis_mcp.auth.requests.post", return_value=resp):
        return totp_login("s", "sch", "u", "JBSWY3DPEHPK3PXP")


def test_student_account_is_own_child():
    s = _login({"elemType": "STUDENT", "elemId": 42, "displayName": "Max", "children": []})
    assert s.children == [{"id": 42, "firstName": "Max"}]


def test_parent_children_untouched():
    kids = [{"id": 7, "firstName": "A"}]
    s = _login({"elemType": "LEGAL_GUARDIAN", "elemId": 1, "children": kids})
    assert s.children == kids
