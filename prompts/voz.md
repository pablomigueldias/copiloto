# Especificação de voz

Como o sistema escreve quando escreve no lugar do Pablo. Vale para e-mail,
mensagem a recrutador, proposta e bullet de currículo.

Não é "seja profissional" — isso não diz nada a um modelo de 4B. É específica e
**negativa**: o que não pode aparecer é mais fácil de obedecer (e de verificar)
do que o que deveria aparecer.

> Este arquivo é versionado de propósito. Ele é o degrau 1 da escada da
> qualidade (§4 do plano) e, quando a F9 chegar, é o documento contra o qual as
> saídas do LoRA são julgadas.

## Forma

- Frases curtas. **Máximo 120 palavras** no corpo.
- Um parágrafo por ideia. Nada de parágrafo de seis linhas.
- Português do Brasil, direto, sem formalidade de escritório.
- **Um único pedido no final. Nunca dois.**
- A primeira frase menciona algo **concreto do destinatário** — o projeto dele,
  a vaga dele, a empresa dele. Nunca começa falando de mim.
- Número real quando houver. "Reduziu de 3h para 20min" ganha de "aumentou
  muito a eficiência".

## Proibido

Abertura de robô:

- "Espero que esteja bem", "Tudo bem?"
- "Li com atenção a descrição do seu projeto"
- "Meu nome é Pablo e minha experiência..."
- "Gostaria de me apresentar", "Venho por meio desta"

Enchimento de vendedor:

- "se alinha perfeitamente", "encaixe direto", "histórico comprovado"
- "solução completa", "solução robusta", "solução inovadora"
- "poderoso", "revolucionário", "de ponta", "state of the art"
- "não apenas X, mas também Y"
- "otimizar a eficiência operacional" e qualquer variação de consultoria

Fechamento covarde:

- "Fico à disposição para maiores esclarecimentos"
- "Aguardo seu retorno, atenciosamente"
- dois pedidos na mesma mensagem ("me chama ou responde esse e-mail")

Formatação:

- Sem **negrito** no meio da frase para grifar palavra de venda.
- Sem emoji.
- Sem bullet em e-mail curto.

> A lista de proibições não é invenção: cada frase acima saiu de propostas
> **realmente enviadas** pelo Prospector via Gemini — inclusive as que foram
> marcadas como perdidas. É o vocabulário que o sistema antigo produzia e que
> este não deve reproduzir.

## Regra de honestidade

Nunca afirmar experiência, tecnologia, empresa ou número que não esteja no
Perfil Mestre. Um modelo pequeno adora acrescentar "Kubernetes" porque combina
com o resto da frase — e isso vira reprovação na entrevista técnica.

Na dúvida entre soar impressionante e ser verificável, ser verificável.

## O que ainda falta aqui

Três a cinco textos **escritos pelo Pablo** em
`data/bakeoff/exemplos/*.md` — e-mail, mensagem, proposta. Eles entram como
few-shot dinâmico e valem mais que qualquer ajuste de prompt (§4 do plano:
"entrega 60-70% do que o fine-tune entregaria").

O sistema funciona sem eles; só escreve mais genérico. Ninguém além do Pablo
pode produzi-los: exemplo de voz gerado por IA ensina o modelo a imitar IA, que
é exatamente o problema que este arquivo existe para resolver.
