"""Verificador específico desta entrega parcial: hashes, estrutura e credenciais."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
from xml.etree import ElementTree
import zipfile

import fitz

ROOT = Path("/app")
OUT = ROOT / "entrega_pessoa_2"


def main():
    required = ["rotas_api.csv", "latencia_busca.csv", "redis_metricas.csv",
                "resultado_busca.json", "teste_carrinho.txt", "teste_ldap.txt",
                "teste_kerberos.txt", "teste_perfis_403.txt", "texto_secoes_5_6_7.docx",
                "STATUS.md", "manifesto.json", "navegador_verificacoes.json"]
    assert all((OUT / name).is_file() for name in required)
    manifest = json.loads((OUT / "manifesto.json").read_text())
    for category, directory in [("arquivos_fonte_sha256", ROOT), ("evidencias_sha256", OUT)]:
        for name, expected in manifest[category].items():
            assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected, name
    states = json.loads((OUT / "verificacoes.json").read_text())
    assert len(states) == 14
    assert len(list(csv.DictReader((OUT / "rotas_api.csv").open()))) == 14
    if manifest["estado"].startswith("PARCIAL"):
        assert not list(csv.DictReader((OUT / "latencia_busca.csv").open()))
        assert not list(csv.DictReader((OUT / "redis_metricas.csv").open()))
        assert len([entry for entry in states if entry["resultado"] == "APROVADO"]) == 4
    assert re.search(r"\b33 passed\b", (OUT / "pytest.txt").read_text())
    assert "built in" in (OUT / "frontend_build.txt").read_text()
    assert len(list((OUT / "prints_frontend").glob("*.png"))) >= 2
    assert len(list((OUT / "prints_swagger").glob("*.png"))) >= 4
    with zipfile.ZipFile(OUT / "texto_secoes_5_6_7.docx") as archive:
        document = archive.read("word/document.xml")
        ElementTree.fromstring(document)
        assert b"PARCIAL" in document
        extra_text = [document]
    pdf = fitz.open(OUT / "exportacao_vazia.pdf")
    assert len(pdf) >= 1
    pdf.close()
    values = [os.environ[name].encode() for name in [
        "API_SECRET", "REDIS_PASSWORD", "LDAP_PASSWORD", "KRB5_KDC_MASTER_PASSWORD",
        "EVAL_STUDENT_PASSWORD", "EVAL_TEACHER_PASSWORD"] if os.environ.get(name)]
    jwt_pattern = re.compile(rb"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}")
    for path in OUT.rglob("*"):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        assert all(value not in raw for value in values), "Possível segredo em " + path.name
        if path.suffix in {".json", ".md", ".txt", ".csv"}:
            assert not jwt_pattern.search(raw), "Possível JWT em " + path.name
    for raw in extra_text:
        assert all(value not in raw for value in values), "Possível segredo no DOCX"
        assert not jwt_pattern.search(raw), "Possível JWT no DOCX"
    print("Entrega PARCIAL verificada: 14 estados, hashes corretos, DOCX/PDF/PNG válidos e nenhuma credencial detectada.")


if __name__ == "__main__":
    main()
