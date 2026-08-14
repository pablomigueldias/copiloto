"""O verificador de voz — a parte da qualidade que o código consegue conferir."""
from app.llm.voz import checar, texto_da_spec

BOM = (
    "Vi que a clínica tem três unidades e agenda cheia. Fiz um sistema que "
    "confirma consulta por WhatsApp e derrubou a falta de paciente de 30% para "
    "12% num consultório do mesmo porte. Quer ver funcionando em 10 minutos?"
)


def test_texto_dentro_da_spec_passa():
    assert checar(BOM) == []


def test_spec_existe_e_tem_conteudo():
    assert "Proibido" in texto_da_spec()


def test_pega_abertura_de_robo():
    assert checar("Espero que esteja bem. Segue a proposta.")


def test_pega_enchimento_de_vendedor():
    # Frase real de proposta enviada pelo sistema antigo.
    p = checar("Minha experiência se alinha perfeitamente a esse desafio.")
    assert any("vendedor" in x for x in p)


def test_pega_dois_pedidos():
    p = checar("Faz sentido conversar? Prefere que eu mande um resumo antes?")
    assert any("pergunta" in x for x in p)


def test_pega_texto_longo():
    p = checar(" ".join(["palavra"] * 200))
    assert any("máximo" in x for x in p)


def test_pega_emoji_e_negrito():
    assert any("emoji" in x for x in checar("Bom dia 🚀"))
    assert any("negrito" in x for x in checar("Entrego uma **solução** rápida."))


def test_max_palavras_configuravel():
    texto = " ".join(["palavra"] * 40)
    assert checar(texto) == []
    assert checar(texto, max_palavras=30)
