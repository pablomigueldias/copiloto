# Voz de post para o dono de negócio (pilar `automacao-negocio`)

Complementa a `voz-post.md`, que continua valendo inteira: cena na abertura,
número no lugar de adjetivo, um pedido só, nada inventado, `{{FALTA: …}}` onde
a matéria-prima não tem o fato. Aqui muda **quem lê**.

O leitor é o dono de uma clínica de psicologia com equipe (D11, D13): decide
entre uma sessão e outra, lê no celular, não é da área de tecnologia e **não
precisa ser**. Ele não quer entender como o atendente funciona por dentro; quer
saber quanto paciente está perdendo e o que dá para fazer amanhã.

## O que muda em relação ao post técnico

- **O "como" não é código, é o que ele faz sozinho.** Um passo a passo
  numerado (no mínimo 3 passos) ou um texto pronto para copiar, em bloco
  ```` ```text ````. Ex.: a mensagem de ausência do WhatsApp Business, com o
  texto inteiro. Se o passo depende de mim para ser feito, não é o "como" do post.
- **Número antes de conceito.** Primeiro "51% querem resposta em até 5 minutos",
  depois o que isso quer dizer para a agenda dele. Nunca o contrário.
- **O exemplo é o dia dele:** o paciente que escreve às 22h, a recepção que sai
  às 18h, a falta de segunda de manhã, o psicólogo respondendo WhatsApp entre
  sessões. Não é "uma empresa", "um usuário", "um cliente final".
- **A fonte é de fora e ele pode conferir:** pesquisa com nome e ano (TIC Saúde
  2023, CX Trends 2026), a norma do conselho com o número (Res. CFP 9/2024).
  Link para a fonte, não para o meu repositório.
- **Fecho: um próximo passo que custa pouco para ele.** O raio-x gratuito, a
  newsletter ou o checklist. Um só. Com `<CTA assunto="…" />`, o convite do
  pilar já diz "Quer saber onde o seu WhatsApp está perdendo cliente?".

## Sem jargão

O verificador aponta estas palavras na prosa quando aparecem **sem explicação**
logo depois, entre parênteses. Código e texto entre crases não contam.

| Não escreva | Escreva |
|---|---|
| lead | paciente novo, quem pediu horário |
| funil, conversão, churn | quantos marcaram, quantos voltaram, quantos saíram |
| chatbot, bot | atendente automático, o atendente |
| LLM, modelo de linguagem, IA generativa, RAG, embedding, prompt, token | "a IA" basta; se precisar, diga o que ela faz |
| API, webhook, integração via API, backend, deploy | "ligado à sua agenda", "no ar" |
| pipeline, dashboard, stack, SaaS, onboarding | o que acontece, em palavras dele |

Quando a palavra técnica **é** o assunto (ex.: "API oficial da Meta", que ele
vai ver no contrato), explique na primeira vez: "API oficial da Meta (o jeito
que a Meta autoriza empresas a usar o WhatsApp com um sistema)".

## O que o conselho proíbe (e o post também)

Vale para a psicologia (`data/comercial/base/publico.md`, restrições):

- Nada de promessa de resultado ("nunca mais perca um paciente").
- Nada de "acolhimento", "escuta" ou "triagem" feitos pelo atendente: ele é
  secretária, nunca terapeuta.
- Preço de sessão, desconto, "valor social": não entram em exemplo nenhum.
- Caso de paciente real, nem anônimo: o exemplo é inventado **e diz que é**
  ("imagine uma clínica com 4 psicólogos"), ou é número de pesquisa.

## Tamanho e forma

- 500 a 900 palavras: menor que o técnico. Leitura de 3 a 4 minutos no celular.
- Parágrafo de até 3 linhas.
- Subtítulos que respondem uma pergunta dele ("Quanto custa deixar para
  amanhã", e não "Contexto").
