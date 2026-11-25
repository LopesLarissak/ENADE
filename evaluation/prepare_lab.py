"""Cria credenciais efêmeras locais. Nunca imprime nem versiona os valores."""
import os
from pathlib import Path
import re
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    private = root / ".evaluation-private"
    private.mkdir(mode=0o700, exist_ok=True)
    env = root / ".env.evaluation"
    if env.exists():
        raise SystemExit("Ambiente já preparado; reutilize-o sem regenerar identidades.")
    values = {
        "API_SECRET": secrets.token_hex(32),
        "REDIS_PASSWORD": secrets.token_hex(24),
        "LDAP_PASSWORD": secrets.token_hex(24),
        "KRB5_KDC_MASTER_PASSWORD": secrets.token_hex(24),
        "EVAL_STUDENT_PASSWORD": secrets.token_hex(20),
        "EVAL_TEACHER_PASSWORD": secrets.token_hex(20),
        "ELASTIC_PASSWORD": secrets.token_hex(24),
    }
    ldif = (root / "infra/ldap/01-base.ldif").read_text()
    replacements = iter([values["EVAL_STUDENT_PASSWORD"], values["EVAL_TEACHER_PASSWORD"]])
    ldif = re.sub(r"(?m)^userPassword:.*$", lambda _: "userPassword: " + next(replacements), ldif)
    ldap = private / "ldap"
    ldap.mkdir(exist_ok=True)
    (ldap / "01-base.ldif").write_text(ldif)
    env.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    os.chmod(env, 0o600)
    print("Laboratório preparado; valores confidenciais omitidos.")


if __name__ == "__main__":
    main()
