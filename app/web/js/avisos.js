/* Avisos e perguntas — no lugar de `alert()` e `prompt()`.
 *
 * ## Por que trocar
 *
 * `alert()` **trava a aba inteira**, incluindo o timer de refresco e qualquer
 * requisição em andamento. Durante uma geração de currículo de 60 s isso não é
 * detalhe de estilo: é o sistema parando de responder até eu clicar em OK.
 *
 * E `prompt()` para o motivo da rejeição era pior ainda — o motivo vira sinal
 * de treino, então é um campo importante servido numa caixinha de uma linha
 * sem estilo, que alguns navegadores bloqueiam por padrão.
 *
 * ## As três regras que o formato segue
 *
 * 1. **Erro não some sozinho.** Aviso de erro que desaparece em 5 s é aviso que
 *    eu não li. Some quando eu fechar.
 * 2. **Sucesso some.** Confirmar que deu certo é útil por três segundos.
 * 3. **Aviso pode ter ação.** "Currículo pronto — abrir PDF" vale mais que
 *    "Currículo pronto", principalmente quando eu fechei a gaveta e o resultado
 *    não tem mais para onde voltar.
 */
import { $, escapar } from "./ui.js";

const SEGUNDOS_ATE_SUMIR = { ok: 4000, info: 5000, erro: 0 };

function caixa() {
  let el = $("avisos");
  if (!el) {
    el = document.createElement("div");
    el.id = "avisos";
    document.body.appendChild(el);
  }
  return el;
}

function mostrar(tipo, texto, { detalhe, acao, href, aoClicar } = {}) {
  const aviso = document.createElement("div");
  aviso.className = `aviso-caixa ${tipo}`;
  aviso.setAttribute("role", tipo === "erro" ? "alert" : "status");

  const botaoAcao = acao
    ? href
      ? `<a class="aviso-acao" href="${escapar(href)}" target="_blank" rel="noopener">${escapar(acao)}</a>`
      : `<button class="aviso-acao">${escapar(acao)}</button>`
    : "";

  aviso.innerHTML = `
    <div class="aviso-texto">
      <b>${escapar(texto)}</b>
      ${detalhe ? `<span class="aviso-detalhe">${escapar(detalhe)}</span>` : ""}
    </div>
    ${botaoAcao}
    <button class="aviso-fechar" title="fechar">✕</button>`;

  const fechar = () => {
    aviso.dataset.saindo = "1";
    setTimeout(() => aviso.remove(), 180);
  };
  aviso.querySelector(".aviso-fechar").addEventListener("click", fechar);
  if (aoClicar) {
    aviso.querySelector(".aviso-acao")?.addEventListener("click", () => {
      fechar();
      aoClicar();
    });
  }

  caixa().appendChild(aviso);
  const prazo = SEGUNDOS_ATE_SUMIR[tipo];
  if (prazo) setTimeout(fechar, prazo);
  return fechar;
}

export const ok = (texto, opcoes) => mostrar("ok", texto, opcoes);
export const info = (texto, opcoes) => mostrar("info", texto, opcoes);
export const erro = (texto, opcoes) => mostrar("erro", texto, opcoes);

/**
 * Pergunta alguma coisa numa caixa de verdade. Devolve o texto, ou `null` se
 * eu desistir — a mesma assinatura do `prompt()` que ela substitui.
 */
export function perguntar(titulo, { descricao, multilinha, confirmar = "ok" } = {}) {
  return new Promise((resolver) => {
    const fundo = document.createElement("div");
    fundo.className = "modal-fundo";
    fundo.innerHTML = `
      <form class="modal" method="dialog">
        <h3>${escapar(titulo)}</h3>
        ${descricao ? `<p>${escapar(descricao)}</p>` : ""}
        ${multilinha ? '<textarea rows="4" autofocus></textarea>' : '<input autofocus>'}
        <div class="modal-botoes">
          <button type="button" class="ghost" data-acao="cancelar">cancelar</button>
          <button type="submit" class="primario">${escapar(confirmar)}</button>
        </div>
      </form>`;

    const campo = fundo.querySelector("textarea, input");
    const encerrar = (valor) => {
      fundo.remove();
      document.removeEventListener("keydown", aoTeclar);
      resolver(valor);
    };
    const aoTeclar = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();          // não deixa fechar a gaveta atrás
        encerrar(null);
      }
    };

    fundo.querySelector("form").addEventListener("submit", (e) => {
      e.preventDefault();
      encerrar(campo.value.trim());
    });
    fundo.querySelector('[data-acao="cancelar"]').addEventListener("click", () => encerrar(null));
    // Clicar fora cancela; clicar dentro, não.
    fundo.addEventListener("click", (e) => e.target === fundo && encerrar(null));
    document.addEventListener("keydown", aoTeclar);

    document.body.appendChild(fundo);
    campo.focus();
  });
}

/** Sim ou não. Devolve `true`/`false`, nunca lança. */
export async function confirmar(titulo, { descricao, confirmar: rotulo = "confirmar" } = {}) {
  return new Promise((resolver) => {
    const fundo = document.createElement("div");
    fundo.className = "modal-fundo";
    fundo.innerHTML = `
      <div class="modal">
        <h3>${escapar(titulo)}</h3>
        ${descricao ? `<p>${escapar(descricao)}</p>` : ""}
        <div class="modal-botoes">
          <button type="button" class="ghost" data-acao="nao">cancelar</button>
          <button type="button" class="primario" data-acao="sim">${escapar(rotulo)}</button>
        </div>
      </div>`;
    const encerrar = (v) => {
      fundo.remove();
      resolver(v);
    };
    fundo.querySelector('[data-acao="sim"]').addEventListener("click", () => encerrar(true));
    fundo.querySelector('[data-acao="nao"]').addEventListener("click", () => encerrar(false));
    fundo.addEventListener("click", (e) => e.target === fundo && encerrar(false));
    document.body.appendChild(fundo);
    fundo.querySelector('[data-acao="sim"]').focus();
  });
}
