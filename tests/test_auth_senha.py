import pytest

from app.api.services.auth import senha_service


def test_hash_nao_guarda_a_senha():
    h = senha_service.hash_senha("uma-senha-bem-forte-2026")
    assert "uma-senha-bem-forte-2026" not in h
    assert h.startswith("$argon2id$")


def test_confere_a_senha_certa_e_recusa_a_errada():
    h = senha_service.hash_senha("uma-senha-bem-forte-2026")
    assert senha_service.conferir_senha(h, "uma-senha-bem-forte-2026")
    assert not senha_service.conferir_senha(h, "outra-coisa-qualquer")


def test_hash_none_retorna_false_sem_explodir():
    """Caminho do anti-timing: usuário inexistente gasta CPU e retorna False."""
    assert not senha_service.conferir_senha(None, "qualquer-coisa")


@pytest.mark.parametrize(
    "senha",
    ["curta", "123456789012", "password", "aaaaaaaaaaaaaa"],
)
def test_recusa_senha_fraca(senha):
    with pytest.raises(senha_service.SenhaFraca):
        senha_service.validar_forca(senha)


def test_aceita_senha_boa():
    senha_service.validar_forca("uma-senha-bem-forte-2026")
