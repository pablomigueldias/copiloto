# Voz de post do blog

A `voz.md` vale para mensagem curta (120 palavras, um pedido). Post é outra
forma: 600 a 1.200 palavras, com código, fórmula e subtítulo. O que continua
igual é o **proibido**: as frases de vendedor e de robô da `voz.md` valem aqui
também, e o verificador reprova as mesmas.

Específica e negativa, pelo mesmo motivo: o que não pode aparecer é mais fácil
de obedecer e de verificar do que "escreva bem".

## Os quatro leitores

O mesmo post é lido por quatro pessoas, e cada uma desiste num ponto diferente:

- **entusiasta** desiste no primeiro parágrafo se ele não for uma cena concreta;
- **cliente** desiste se não houver número com unidade (antes e depois);
- **técnico** desiste se não houver código, fórmula ou estrutura que ele repetiria;
- **recrutador** desiste se não houver prova: link para o repo, de onde o
  conhecimento veio.

## Forma

- Abertura: **uma cena**, até 60 palavras. Uma pergunta que eu fiz, um erro que
  eu vi, um número que me surpreendeu. Nunca "Neste post", "Hoje vou",
  "Vamos falar sobre", "No mundo atual".
- Subtítulos `##` que dizem o que a seção prova, não o tema ("O que separa: a
  distância de cosseno", e não "Resultados").
- Frases curtas. Um parágrafo por ideia, no máximo quatro linhas.
- Número no lugar de adjetivo. "De 12 s para 0,2 s" e não "muito mais rápido".
- Código: só o trecho que importa, com linguagem no bloco (```python). Sem
  credencial, caminho de máquina ou IP — use `SEU_TOKEN_AQUI`, `docs/fase03.md`.
- Fechamento: **um pedido só**, com link. "Tem um RAG que nunca diz 'não sei'?
  [Me chama](/contato)." Nunca dois caminhos.
- Português do Brasil, primeira pessoa, sem formalidade.
- Sem emoji. Sem negrito para grifar palavra de venda.

## Regra de honestidade

A matéria-prima é uma **nota de estudo** ou um **doc de fase**. Nota de aula
reformatada não é post: o Google trata como conteúdo raso e o leitor percebe.
O que transforma uma na outra é experiência própria — um projeto, uma medida,
um erro, uma opinião defendida.

Onde a experiência própria não estiver na matéria-prima, **não invente**.
Escreva o marcador e siga:

    {{FALTA: que número eu medi aqui?}}

Nunca invente número, empresa, cliente, tecnologia ou resultado. Um marcador
aberto custa um minuto meu; um número inventado custa a credibilidade do blog.

**Isso vale em dobro para a cena da abertura e para qualquer frase em primeira
pessoa.** "Perguntei ao meu assistente…", "No meu projeto…", "Quando eu testei…"
só podem aparecer se o fato está na matéria-prima. Se não está, a abertura é:

    {{FALTA: que situação real minha abre este post? (uma pergunta, um erro, um número)}}

seguida do resto do texto. Uma cena inventada em primeira pessoa é mentira
assinada por mim — pior que um post sem cena.

## Componentes que o blog entende

- `<Callout tipo="nota">…</Callout>` para um aviso curto (tipos: nota, dica, cuidado).
- `<CTA assunto="busca híbrida" />` no fechamento, quando o pedido for o
  contato. O `assunto` entra na mensagem pré-preenchida do WhatsApp.
- Fórmula em `$$ … $$` (KaTeX). Diagrama em bloco ```mermaid.
