"""Bake-off: o mesmo prompt em vários modelos, para julgar às cegas.

Trocar de modelo base custa um `ollama pull`. Treinar um LoRA custa meses de
coleta. Testar primeiro é a ordem óbvia — e o vencedor daqui é o alvo do LoRA
lá na F9.

As saídas são gravadas com nome **anônimo** (`a.md`, `b.md`, ...) e o mapa
modelo↔letra vai para um arquivo separado. Julgar sabendo qual é qual mede a
expectativa sobre o modelo, não o texto que ele escreveu.

Uso:
    python scripts/bakeoff.py                      # modelos padrão, casos padrão
    python scripts/bakeoff.py qwen3:4b gemma3:4b
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.providers.ollama import OllamaProvider  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "bakeoff"
VOZ = SAIDA / "voz.md"          # especificação de voz (escrita pelo Pablo)
EXEMPLOS = SAIDA / "exemplos"   # textos reais dele, um por arquivo

MODELOS_PADRAO = ["qwen3:4b", "gemma3:4b"]

# Um caso de cada tipo que o sistema vai pedir de verdade. Curtos de propósito:
# formato rígido é onde um 4B tem chance real, e é 90% do que o produto precisa.
CASOS = {
    "email_frio": (
        "Escreva um e-mail frio para o dono de uma clínica odontológica de bairro, "
        "com 3 unidades, oferecendo um sistema que confirma consulta por WhatsApp e "
        "reduz falta de paciente. Ele nunca ouviu falar de mim."
    ),
    "msg_recrutador": (
        "Escreva uma mensagem curta para um recrutador de uma vaga de desenvolvedor "
        "backend pleno (Python, FastAPI, Postgres, 100% remota), dizendo por que faz "
        "sentido conversarmos. Tenho um sistema em produção que uso todo dia."
    ),
    "bullet_curriculo": (
        "Reescreva este item de currículo para uma vaga de backend: "
        "'Fiz um pipeline de vídeo com FastAPI que automatiza a produção de Shorts.' "
        "O pipeline tem 6 estágios e derrubou o tempo de produção de 3h para 20min."
    ),
}

VOZ_PADRAO = """- Frases curtas. No máximo 120 palavras no corpo.
- Sem "espero que esteja bem", "gostaria de apresentar", "não apenas X mas também Y".
- Sem adjetivo de venda: inovador, robusto, poderoso, revolucionário, solução completa.
- A primeira frase menciona algo concreto do destinatário.
- Um único pedido no final. Nunca dois.
- Português do Brasil, direto, sem formalidade de escritório."""


def montar_prompt(caso: str) -> str:
    voz = VOZ.read_text().strip() if VOZ.exists() else VOZ_PADRAO
    partes = [
        "Você escreve no lugar do Pablo. Siga a especificação de voz à risca.",
        f"\n## Voz\n{voz}",
    ]
    if EXEMPLOS.exists():
        textos = sorted(EXEMPLOS.glob("*.md")) or sorted(EXEMPLOS.glob("*.txt"))
        if textos:
            amostra = "\n\n---\n\n".join(t.read_text().strip() for t in textos[:3])
            partes.append(f"\n## Exemplos escritos pelo Pablo\n{amostra}")
    partes.append(f"\n## Tarefa\n{caso}\n\nEscreva apenas o texto final.")
    return "\n".join(partes)


async def main() -> None:
    modelos = sys.argv[1:] or MODELOS_PADRAO
    provider = OllamaProvider()
    if not await provider.disponivel():
        sys.exit("Ollama não responde. Rode ./scripts/ollama-serve.sh")

    letras = list("abcdefgh")[: len(modelos)]
    embaralhado = list(zip(letras, modelos, strict=True))
    random.shuffle(embaralhado)

    SAIDA.mkdir(parents=True, exist_ok=True)
    mapa: dict[str, dict] = {}

    for caso, texto in CASOS.items():
        prompt = montar_prompt(texto)
        pasta = SAIDA / caso
        pasta.mkdir(exist_ok=True)
        print(f"\n── {caso}")
        for letra, modelo in embaralhado:
            t0 = time.perf_counter()
            r = await provider.gerar(prompt, modelo=modelo, temperatura=0.7)
            ms = int((time.perf_counter() - t0) * 1000)
            (pasta / f"{letra}.md").write_text(r.texto.strip() + "\n")
            mapa.setdefault(caso, {})[letra] = {
                "modelo": modelo,
                "ms": ms,
                "tokens_saida": r.tokens_output,
                "thinking_chars": len(r.thinking),
                "palavras": len(r.texto.split()),
            }
            print(
                f"   {letra}.md  {ms/1000:>6.1f}s  {len(r.texto.split()):>4} palavras"
                f"  (raciocínio: {len(r.thinking)} chars)"
            )

    (SAIDA / "GABARITO.json").write_text(json.dumps(mapa, indent=2, ensure_ascii=False))

    print(f"\nSaídas em {SAIDA}")
    print("Leia os .md SEM abrir o GABARITO.json, escolha o melhor de cada caso,")
    print("anote a letra, e só então confira quem era quem.")
    if not VOZ.exists():
        print("\n⚠  Sem especificação de voz própria — usando a genérica.")
        print(f"   Escreva a sua em {VOZ} e rode de novo.")
    if not EXEMPLOS.exists():
        print("⚠  Sem exemplos reais — o few-shot é o degrau de maior retorno.")
        print(f"   Ponha 3 textos seus em {EXEMPLOS}/ e rode de novo.")


if __name__ == "__main__":
    asyncio.run(main())
