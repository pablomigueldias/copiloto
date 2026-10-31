Você vai escrever o REFORÇO de um assunto que o Pablo errou no simulado da prova do Instituto Avança SP (CRECI-SP 01/2026, PAS – Analista de TI – Banco de Dados, 29/11/2026). Ele pediu isto pelo botão "Gerar reforço" da tela; ninguém vai responder perguntas suas — trabalhe sozinho e termine.

## O que escrever

Exatamente 5 questões de múltipla escolha (A–E), no padrão das bancas, do assunto:

- simulado nº {simulado}
- matéria: {materia}
- assunto: {assunto}
- rodada: {rodada}

As questões têm de mirar O ENGANO QUE ELE COMETEU, não o assunto em abstrato. Os erros que abriram este reforço:

{erros}

Origens que ele já viu em rodadas anteriores (não repetir a ideia delas):
{ja_usadas}

## Como escrever (regras do acervo — siga todas)

- Leia antes: `scripts/simulado/reforco_base.py` (o molde), `scripts/ineditas_bd/base.py` (helpers `confere`, `AF3`, `TABELAS`) e, como exemplo de estilo, um trecho de `scripts/ineditas_bd/t4.py` e `scripts/avanca_sp/matematica.py`.
- 5 alternativas; enunciado de cenário quando couber; pode usar afirmações I/II/III (`fixa` com `AF3`) e comando NÃO/INCORRETO em caixa alta, como a Avança SP faz.
- Varie a forma de cobrar entre as 5: a mesma regra vista de ângulos diferentes, incluindo exatamente a pegadinha em que ele caiu.
- Explicação em português, SEM negrito (`**` é recusado), começando por reabrir o problema em uma linha, com tabela Markdown quando houver enumeração, nomeando a pegadinha e terminando com o atalho. Use `{G}` no lugar da letra certa.
- Cada questão funciona sozinha (nunca "a questão anterior").
- Gabarito verificado: SQL com `verificar=confere(sql, esperado)` (roda no SQLite com as tabelas de `base.py`); conta com `assert` em Python no próprio arquivo, usando `fractions` quando houver divisão. Português pela norma-padrão e pelo Manual de Redação da Presidência (3ª ed.) — nada discutível entre gramáticos. Inglês técnico no padrão de `docs/avanca-sp/ingles-tecnico-padrao.md`.

## Os passos, nesta ordem

1. Crie `{arquivo_py}` com:

   ```python
   import sys; from pathlib import Path
   sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
   from reforco_base import Reforco
   from base import AF3, AF3b, TABELAS, confere   # o que usar
   R = Reforco(simulado={simulado}, nome="{nome}")
   t = R.assunto("{assunto}", rodada={rodada})
   t.mc(...)   # 5 vezes (ou t.fixa)
   R.grava()
   ```

2. Rode `python3 {arquivo_py}` e corrija até gravar sem erro.
3. Rode `.venv/bin/python scripts/simulado/importar_reforco.py {arquivo_json}` — ele precisa dizer "pronto, 5 questões".
4. Responda com uma linha: o que as 5 cobram.

Se algo impedir terminar, responda com a causa em uma linha. Não edite nenhum outro arquivo.
