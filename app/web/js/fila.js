/* A fila de aprovação — onde o sistema aprende.
 *
 * Cada texto aqui é uma proposta do modelo esperando decisão minha. O que eu
 * aprovo vira `exemplo_estilo` (few-shot); o que eu **edito antes de aprovar**
 * vira par de preferência para o fine-tune. É por isso que este é o módulo
 * onde perder um caractere importa mais que em qualquer outro lugar da tela.
 */
import { api } from "./api.js";
import * as aviso from "./avisos.js";
import { $, escapar, haQuanto, ocupado } from "./ui.js";

/** Estou mexendo em algum cartão da fila agora? */
export function emEdicao() {
  const container = $("fila");
  return Boolean(
    container.querySelector('.acao[data-sujo="1"]') ||
      (document.activeElement && container.contains(document.activeElement))
  );
}

/**
 * Repinta a fila — a menos que eu esteja editando alguma coisa nela.
 *
 * O defeito que isto conserta: `innerHTML = ...` a cada 15 s substituía o
 * textarea inteiro, apagando o que eu tinha acabado de escrever, sem aviso.
 *
 * A regra é o bloco inteiro, não o cartão: transplantar cartões preservados
 * para dentro do HTML novo funciona até a ação ser decidida noutra aba, e aí o
 * cartão editado não teria para onde voltar. Cinco cartões parados enquanto eu
 * digito em um deles não custa nada; perder o texto custa.
 */
export function repintar(f) {
  if (emEdicao()) {
    $("fila-pausada").hidden = false;
    return;
  }
  $("fila-pausada").hidden = true;
  $("fila").innerHTML = pintar(f);
}

function pintar(f) {
  $("fila-total").textContent = f.pendentes ?? 0;
  $("fila-total").dataset.zero = f.pendentes ? "0" : "1";
  if (f.erro) return `<p class="falhou">${escapar(f.erro)}</p>`;

  if (!f.itens?.length) {
    const decididas = Object.entries(f.por_status || {})
      .map(([s, n]) => `${n} ${s}`)
      .join(" · ");
    return `<p class="vazio">Nada esperando decisão.</p>${
      decididas ? `<p class="rotulo">${escapar(decididas)}</p>` : ""
    }`;
  }

  return f.itens
    .map((a) => {
      const avisos = (a.payload?.avisos || [])
        .map((x) => `<div class="aviso">⚠ ${escapar(x)}</div>`)
        .join("");
      const rejeitados = (a.payload?.rejeitados || []).length;
      // Currículo se julga vendo o PDF: o link abre o mesmo arquivo que o ATS lê.
      const pdf = a.payload?.vaga_id
        ? `<a class="botao-link" href="/api/vagas/${a.payload.vaga_id}/curriculo.pdf"
              target="_blank" rel="noopener">ver PDF</a>`
        : "";
      return `
      <article class="acao" data-id="${a.id}">
        <div class="topo">
          <span class="titulo">${escapar(a.titulo)}</span>
          <span class="meta">${escapar(a.agente)}/${escapar(a.tipo)}</span>
        </div>
        ${a.contexto ? `<div class="contexto">${escapar(a.contexto)}</div>` : ""}
        <textarea data-campo="texto">${escapar(a.texto_gerado || "")}</textarea>
        ${avisos}
        ${rejeitados ? `<div class="aviso">${rejeitados} trecho(s) removidos pela anti-alucinação</div>` : ""}
        <div class="botoes">
          <button class="aprovar" data-acao="aprovar">aprovar</button>
          <button class="rejeitar" data-acao="rejeitar">rejeitar</button>
          ${pdf}
          <span class="meta" style="margin-left:auto;align-self:center">${haQuanto(a.criada_em)}</span>
        </div>
      </article>`;
    })
    .join("");
}

/** Liga os eventos da fila. `recarregar` é o ciclo do painel. */
export function ligar(recarregar) {
  const fila = $("fila");

  // Digitar marca o cartão como sujo, e cartão sujo não é repintado.
  // `input` e não `change`: `change` só dispara ao sair do campo, e o refresco
  // acontece muito antes disso.
  fila.addEventListener("input", (e) => {
    const cartao = e.target.closest(".acao");
    if (cartao) cartao.dataset.sujo = "1";
  });

  // Sair de um cartão sem ter mexido nele libera o refresco na hora seguinte.
  fila.addEventListener("focusout", () => {
    setTimeout(() => {
      if (!emEdicao()) $("fila-pausada").hidden = true;
    }, 0);
  });

  // "atualizar mesmo assim": eu decido perder o rascunho, não o timer.
  $("btn-forcar-fila").addEventListener("click", async () => {
    fila.querySelectorAll(".acao").forEach((c) => delete c.dataset.sujo);
    document.activeElement?.blur();
    await recarregar().catch((e) => aviso.erro("Não consegui atualizar", { detalhe: e.message }));
  });

  // Decidir da tela. O texto do textarea vai junto: se eu mexi, o serviço
  // classifica como 'editada' e o par vira dado de treino.
  fila.addEventListener("click", async (e) => {
    const botao = e.target.closest("button[data-acao]");
    if (!botao) return;

    const cartao = botao.closest(".acao");
    const decisao = botao.dataset.acao;
    const corpo = { decisao };

    if (decisao === "rejeitar") {
      // O motivo vira sinal de treino: merece um campo de verdade, não a
      // caixinha de uma linha do `prompt()` — que ainda por cima travava a aba.
      const motivo = await aviso.perguntar("Por que rejeitar?", {
        descricao: "O motivo vira sinal de treino — vale escrever o que ficou errado.",
        multilinha: true,
        confirmar: "rejeitar",
      });
      if (motivo === null) return;
      corpo.motivo = motivo;
    } else {
      corpo.texto_final = cartao.querySelector("[data-campo=texto]").value;
    }

    try {
      await ocupado(botao, decisao === "aprovar" ? "aprovando…" : "rejeitando…", () =>
        api(`/api/fila/${cartao.dataset.id}/decidir`, {
          method: "POST",
          body: JSON.stringify(corpo),
        })
      );
      // Decidida: o rascunho virou decisão, então o cartão não é mais sujo e o
      // refresco pode voltar a pintar a fila.
      delete cartao.dataset.sujo;
      document.activeElement?.blur();
      aviso.ok(decisao === "aprovar" ? "Aprovado — virou exemplo de estilo" : "Rejeitado");
      await recarregar();
    } catch (erro) {
      aviso.erro("Não consegui registrar a decisão", { detalhe: erro.message });
    }
  });
}
