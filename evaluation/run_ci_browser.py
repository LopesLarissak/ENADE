"""Executa o navegador sem publicar credenciais em mensagens de erro."""
import os
from pathlib import Path
import re
import subprocess
import sys


def redact(text, values):
    for value in sorted(values, key=len, reverse=True):
        if value:
            text = text.replace(value, "[CREDENCIAL REMOVIDA]")
    text = re.sub(r"\beyJ[A-Za-z0-9_.-]{8,}", "[JWT REMOVIDO]", text)
    text = re.sub(r"Bearer\s+\S+", "Bearer [REMOVIDO]", text)
    return re.sub(r"\b[0-9a-f]{16,}\b", "[IDENTIFICADOR REMOVIDO]", text)


def secret_values():
    keys = {"API_SECRET", "REDIS_PASSWORD", "LDAP_PASSWORD", "KRB5_KDC_MASTER_PASSWORD",
            "EVAL_STUDENT_PASSWORD", "EVAL_TEACHER_PASSWORD", "ELASTIC_PASSWORD"}
    path = Path(".env.evaluation")
    if not path.exists():
        return []
    return [value.strip().strip('"').strip("'")
              for line in path.read_text().splitlines() if "=" in line
              for key, value in [line.split("=", 1)] if key.strip() in keys]


def main():
    values = secret_values()
    command = [
        "docker", "run", "--rm", "--network", "enade-plataforma_default",
        "--env-file", ".env.evaluation",
        "-e", "EVAL_SOURCE_COMMIT=" + os.environ["GITHUB_SHA"],
        "-e", "EVAL_ENVIRONMENT=GitHub Actions ubuntu-24.04, Docker",
        "-v", str(Path.cwd()) + ":/app", "-w", "/app", "enade-evidence-tools:local",
        "sh", "-c", "python -m evaluation.capture_pessoa2 && python -m evaluation.report_pessoa2",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    print(redact(result.stdout + result.stderr, values), end="", flush=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
