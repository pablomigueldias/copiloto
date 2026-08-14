"""Fluxo de autenticação ponta a ponta pelo HTTP."""
from app.api.services.auth.csrf import csrf_cookie_name


async def _login(client, email, senha):
    return await client.post("/api/auth/login", json={"email": email, "senha": senha})


async def test_senha_errada_retorna_401_generico(client, usuario):
    u, _ = usuario
    r = await _login(client, u.email, "senha-errada-mas-longa")
    assert r.status_code == 401
    # Mensagem genérica: não pode denunciar se o email existe.
    assert "senha" in r.json()["detail"].lower()
    assert client.cookies.get("sessao") is None


async def test_email_inexistente_responde_igual(client, usuario):
    r = await _login(client, "nao-existe@copiloto.local", "qualquer-coisa-longa")
    assert r.status_code == 401


async def test_login_valido_abre_sessao(client, usuario):
    u, senha = usuario
    r = await _login(client, u.email, senha)
    assert r.status_code == 200
    assert r.json()["email"] == u.email
    assert client.cookies.get("sessao")
    assert client.cookies.get(csrf_cookie_name())


async def test_me_exige_sessao(client, usuario):
    assert (await client.get("/api/auth/me")).status_code == 401

    u, senha = usuario
    await _login(client, u.email, senha)
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == u.email


async def test_mutacao_com_cookie_exige_csrf(client, usuario):
    u, senha = usuario
    await _login(client, u.email, senha)

    # Sem o header, o middleware barra.
    assert (await client.post("/api/auth/logout")).status_code == 403

    token = client.cookies.get(csrf_cookie_name())
    r = await client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    assert r.status_code == 200


async def test_logout_revoga_a_sessao(client, usuario):
    u, senha = usuario
    await _login(client, u.email, senha)
    token = client.cookies.get(csrf_cookie_name())
    sessao = client.cookies.get("sessao")

    await client.post("/api/auth/logout", headers={"X-CSRF-Token": token})

    # O cookie antigo não vale mais nem se for reapresentado: a sessão está
    # revogada no servidor (é o que JWT não consegue fazer).
    client.cookies.set("sessao", sessao)
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_troca_de_senha_invalida_a_senha_antiga(client, usuario):
    u, senha = usuario
    await _login(client, u.email, senha)
    headers = {"X-CSRF-Token": client.cookies.get(csrf_cookie_name())}

    nova = "outra-senha-bem-forte-2026"
    r = await client.post(
        "/api/auth/senha",
        json={"senha_atual": senha, "senha_nova": nova},
        headers=headers,
    )
    assert r.status_code == 200

    client.cookies.clear()
    assert (await _login(client, u.email, senha)).status_code == 401
    assert (await _login(client, u.email, nova)).status_code == 200


async def test_troca_de_senha_recusa_senha_fraca(client, usuario):
    u, senha = usuario
    await _login(client, u.email, senha)
    headers = {"X-CSRF-Token": client.cookies.get(csrf_cookie_name())}

    r = await client.post(
        "/api/auth/senha",
        json={"senha_atual": senha, "senha_nova": "123456"},
        headers=headers,
    )
    assert r.status_code == 400


async def test_excesso_de_tentativas_bloqueia(client, usuario):
    """Lockout por conta: 5 falhas na janela → 429 mesmo com a senha certa."""
    u, senha = usuario
    for _ in range(5):
        assert (await _login(client, u.email, "errada-mas-longa-o-bastante")).status_code == 401
    assert (await _login(client, u.email, senha)).status_code == 429
