from types import SimpleNamespace
from app.api import auth

class FakeConnection:
    def __init__(self, server, user=None, password=None, **kwargs):
        self.user, self.password = user, password
        self.entries, self.result = [], {"result": 0, "description": "success"}
    def bind(self):
        ok = self.password == ("service-password" if self.user.startswith("cn=") else "valid-password")
        self.result = {"result": 0 if ok else 49, "description": "success" if ok else "invalidCredentials"}
        return ok
    def search(self, search_base, search_filter, search_scope, attributes):
        if search_base.startswith("ou=people"):
            self.entries = [SimpleNamespace(entry_dn="uid=test,ou=people,dc=example,dc=org")]
        else:
            self.entries = [SimpleNamespace(cn="professores")] if "uid=test" in search_filter else []
        self.search_filter = search_filter
        return True
    def unbind(self): pass

def configure(monkeypatch):
    monkeypatch.setattr(auth, "LDAP_USER_DN", "cn=service,dc=example,dc=org")
    monkeypatch.setattr(auth, "LDAP_PASSWORD", "service-password")
    monkeypatch.setattr(auth, "LDAP_USER_BASE", "ou=people,dc=example,dc=org")
    monkeypatch.setattr(auth, "Connection", FakeConnection)
    monkeypatch.setattr(auth, "Server", lambda host, **kwargs: host)

def test_authenticate_teacher(monkeypatch):
    configure(monkeypatch)
    assert auth.authenticate_ldap("test", "valid-password") == {"username": "test", "role": "PROFESSOR"}

def test_authenticate_rejects_bad_password(monkeypatch):
    configure(monkeypatch)
    assert auth.authenticate_ldap("test", "wrong") is None

def test_authenticate_escapes_filter(monkeypatch):
    configure(monkeypatch)
    auth.authenticate_ldap("test*)(uid=*)", "valid-password")

def test_authenticate_rejects_empty(monkeypatch):
    configure(monkeypatch)
    assert auth.authenticate_ldap("", "x") is None
    assert auth.authenticate_ldap("x", "") is None
