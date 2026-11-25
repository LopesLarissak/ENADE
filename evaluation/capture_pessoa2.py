"""Playwright contra frontend/Swagger reais; sem HAR, vídeos ou traces com segredos."""
import json
import argparse
import os
from pathlib import Path
import re
from playwright.sync_api import sync_playwright, expect

OUT = Path("/app/entrega_pessoa_2")
FRONT = os.getenv("EVAL_FRONT_URL", "http://frontend:5173")
API = os.getenv("EVAL_API_URL", "http://api:8000")


def redact(page, credential):
    """Redação apenas de credenciais, preservando respostas, identidades e status."""
    page.locator(".curl-command, .request-snippets").evaluate_all(
        "elements => elements.forEach(el => { el.textContent = 'Comando omitido para proteger credenciais.'; })")
    page.evaluate("""value => {
      for (const input of document.querySelectorAll('input, textarea'))
        if (input.value.includes(value)) input.value = '[CREDENCIAL REMOVIDA]';
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode()))
        if (node.textContent.includes(value))
          node.textContent = node.textContent.split(value).join('[CREDENCIAL REMOVIDA]');
    }""", credential)
    visible = page.locator("body").inner_text()
    assert credential not in visible
    assert all(piece not in visible for piece in credential.split(".") if len(piece) > 20)


def swagger(page, path, bearer, expected, filename):
    page.goto(API + "/docs")
    expect(page.locator(".opblock").first).to_be_visible(timeout=60000)
    page.get_by_role("button", name="Authorize", exact=False).first.click()
    dialog = page.locator(".dialog-ux")
    dialog.locator('input[type="text"]').fill(bearer)
    dialog.get_by_role("button", name="Apply credentials", exact=True).click()
    dialog.get_by_role("button", name="Close", exact=True).click()
    path_locator = page.locator(".opblock-summary-path").filter(has_text=re.compile("^" + re.escape(path) + "$"))
    block = page.locator(".opblock").filter(has=path_locator)
    block.locator(".opblock-summary").click()
    block.get_by_role("button", name="Try it out").click()
    block.get_by_role("button", name="Execute", exact=True).click()
    live = block.locator(".live-responses-table")
    expect(live.locator("tbody .response-col_status")).to_contain_text(str(expected), timeout=30000)
    redact(page, bearer)
    block.screenshot(path=str(OUT / "prints_swagger" / filename))
    return {"rota": path, "http_confirmado_na_tela": expected, "arquivo": "prints_swagger/" + filename}


def main(auth_only=False):
    for folder in ["prints_swagger", "prints_frontend"]:
        (OUT / folder).mkdir(exist_ok=True)
    records = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=[
            "--disable-dev-shm-usage", "--disable-gpu", "--renderer-process-limit=1"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        docs = context.new_page()
        docs.goto(API + "/docs")
        expect(docs.locator(".opblock").first).to_be_visible(timeout=60000)
        docs.screenshot(path=str(OUT / "prints_swagger/01_rotas.png"), full_page=True)
        for username, role, env_key in [("estudante", "ESTUDANTE", "EVAL_STUDENT_PASSWORD"),
                                         ("professor", "PROFESSOR", "EVAL_TEACHER_PASSWORD")]:
            page.goto(FRONT)
            if page.get_by_role("button", name="Sair", exact=True).is_visible():
                page.get_by_role("button", name="Sair", exact=True).click()
            page.get_by_label("Usuário", exact=True).fill(username)
            page.get_by_label("Senha", exact=True).fill(os.environ[env_key])
            with page.expect_response(lambda response: response.url.endswith("/auth/login")) as login:
                page.get_by_role("button", name="Entrar", exact=True).click()
            assert login.value.status == 200
            expect(page.locator(".account")).to_contain_text(username + " · " + role)
            if auth_only:
                bearer = page.evaluate("localStorage.getItem('enade-token')")
                identity_response = context.request.get(API + "/auth/me", headers={"Authorization": "Bearer " + bearer})
                identity = identity_response.json()
                assert identity == {"username": username, "role": role}
                records.append(swagger(docs, "/auth/me", bearer, 200, f"03_identidade_{username}.png"))
                if role == "ESTUDANTE":
                    records.append(swagger(docs, "/analytics/courses", bearer, 403, "02_estudante_403.png"))
                    page.evaluate("""() => localStorage.setItem('enade-user',
                        JSON.stringify({username: 'professor', role: 'PROFESSOR'}))""")
                    page.reload()
                    expect(page.locator(".account")).to_contain_text("estudante · ESTUDANTE")
                page.screenshot(path=str(OUT / f"prints_frontend/{username}_autenticado.png"), full_page=True)
                records.append({"usuario": username, "identidade_api": identity, "login_http": 200,
                                "escopo": "somente autenticação e perfil; busca e carrinho não validados"})
                page.get_by_role("button", name="Sair", exact=True).click()
                expect(page.get_by_label("Usuário", exact=True)).to_be_visible()
                continue
            page.get_by_placeholder("Tema, enunciado, fórmula ou competência").fill("tecnologia")
            with page.expect_response(lambda response: "/questions?" in response.url) as search:
                page.get_by_role("button", name="Buscar", exact=True).click()
            assert search.value.status == 200
            expect(page.locator("article")).to_have_count(10)
            expect(page.locator("article mark").first).to_be_visible()
            bearer = page.evaluate("localStorage.getItem('enade-token')")
            identity_response = context.request.get(API + "/auth/me", headers={"Authorization": "Bearer " + bearer})
            identity = identity_response.json()
            assert identity == {"username": username, "role": role}
            if role == "ESTUDANTE":
                assert page.locator(".answer-key").count() == 0
                records.append(swagger(docs, "/analytics/courses", bearer, 403, "02_estudante_403.png"))
                # Tentar forjar o perfil no armazenamento não deve alterar a identidade real.
                page.evaluate("""() => localStorage.setItem('enade-user',
                    JSON.stringify({username: 'professor', role: 'PROFESSOR'}))""")
                page.reload()
                expect(page.locator(".account")).to_contain_text("estudante · ESTUDANTE")
                page.get_by_placeholder("Tema, enunciado, fórmula ou competência").fill("tecnologia")
                page.get_by_role("button", name="Buscar", exact=True).click()
                expect(page.locator("article")).to_have_count(10)
            else:
                expect(page.locator(".answer-key")).to_have_count(10)
                page.get_by_role("button", name="Carregar indicadores por curso").click()
                expect(page.get_by_label("Indicadores por curso")).to_contain_text("Sistemas de Informação")
                records.append(swagger(docs, "/analytics/courses", bearer, 200, "04_professor_200.png"))
            records.append(swagger(docs, "/auth/me", bearer, 200, f"03_identidade_{username}.png"))
            page.locator("article").first.get_by_role("button", name="Adicionar à lista").click()
            expect(page.get_by_role("button", name="Minha lista (1)", exact=True)).to_be_visible()
            page.reload()
            expect(page.locator(".account")).to_contain_text(username + " · " + role)
            page.get_by_role("button", name="Minha lista", exact=False).click()
            expect(page.locator(".cart-row")).to_have_count(1)
            page.get_by_placeholder("Tema, enunciado, fórmula ou competência").fill("tecnologia")
            page.get_by_role("button", name="Buscar", exact=True).click()
            expect(page.locator("article")).to_have_count(10)
            if role == "PROFESSOR":
                page.get_by_role("button", name="Carregar indicadores por curso").click()
                expect(page.get_by_label("Indicadores por curso")).to_contain_text("course")
                for kind in ["JSON", "PDF"]:
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Exportar " + kind, exact=True).click()
                    assert download.value.suggested_filename == "simulado-enade." + kind.lower()
                    assert download.value.failure() is None
            page.screenshot(path=str(OUT / f"prints_frontend/{username}_busca_e_sessao.png"), full_page=True)
            records.append({"usuario": username, "identidade_api": identity, "login_http": 200,
                            "busca_http": search.value.status, "carrinho_apos_reload": True,
                            "gabarito_visivel": role == "PROFESSOR", "exportacao_navegador": role == "PROFESSOR"})
            page.get_by_role("button", name="Sair", exact=True).click()
            expect(page.get_by_label("Usuário", exact=True)).to_be_visible()
        browser.close()
    (OUT / "navegador_verificacoes.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    if auth_only:
        print("Chromium: LDAP, identidades/perfis e 403 confirmados; busca, sessão e downloads NÃO validados.")
    else:
        print("Frontend e Swagger: identidades, 403/200, busca, sessão e downloads confirmados no Chromium.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth-only", action="store_true")
    main(parser.parse_args().auth_only)
