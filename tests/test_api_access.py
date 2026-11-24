import jwt
import pytest
from fastapi import HTTPException
from app.api import main

@pytest.mark.parametrize("role,expected", [("ESTUDANTE", 403), ("PROFESSOR", 200)])
def test_professor_route_role_gate(monkeypatch, role, expected):
    secret = "test-secret-with-at-least-32-characters-long"
    monkeypatch.setattr(main, "API_SECRET", secret)
    token = jwt.encode({"sub": "user", "role": role, "typ": "access", "exp": 4102444800}, secret, algorithm="HS256")
    if expected == 403:
        with pytest.raises(HTTPException) as error:
            main.professor(f"Bearer {token}")
        assert error.value.status_code == 403
    else:
        assert main.professor(f"Bearer {token}")["role"] == "PROFESSOR"
