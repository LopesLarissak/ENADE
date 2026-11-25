"""Diagnóstico técnico no log do CI, com remoção de credenciais."""
import subprocess
from evaluation.run_ci_browser import redact, secret_values


def main():
    compose = ["docker", "compose", "--env-file", ".env.evaluation",
               "-f", "docker-compose.yml", "-f", "evaluation/compose.lab.yml"]
    values = secret_values()
    commands = [
        compose + ["ps", "-a"],
        compose + ["logs", "--no-color", "--tail", "80",
                   "elasticsearch", "kafka", "kerberos", "api", "redis", "openldap"],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=40, check=False)
            print(redact(result.stdout + result.stderr, values), end="", flush=True)
        except (OSError, subprocess.TimeoutExpired):
            print("Diagnóstico desta operação indisponível; consulte o estado do job.")


if __name__ == "__main__":
    main()
