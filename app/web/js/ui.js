/* Utilidades de tela — o que todo módulo usa e ninguém deveria reescrever.
 *
 * Módulos ES nativos, sem build: o navegador resolve os `import`. É a decisão
 * da fase-painel.md §2 um degrau acima — o `painel.js` tinha passado de 730
 * linhas, que é o limite do que se lê sem rolar procurando.
 */

export const $ = (id) => document.getElementById(id);

/** Texto vindo do servidor nunca entra em `innerHTML` sem passar por aqui. */
export const escapar = (t) =>
  String(t ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );

export function haQuanto(iso) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 90) return "agora";
  if (s < 3600) return `há ${Math.round(s / 60)} min`;
  if (s < 86400) return `há ${Math.round(s / 3600)} h`;
  return `há ${Math.round(s / 86400)} d`;
}

export const arquivo = (caminho) => String(caminho || "").split("/").pop();

export const data = (iso) =>
  iso ? new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "—";

/** `?refresco=1500` encurta o ciclo — existe para os testes de navegador. */
export const REFRESCO_MS =
  Number(new URLSearchParams(location.search).get("refresco")) || 15_000;

/**
 * Roda uma operação com o botão contando o que está acontecendo.
 *
 * O padrão que faltava: `analisar + gerar` leva ~60 s, e a tela dizia isso com
 * uma frase parada. Botão que não muda enquanto trabalha é botão que parece
 * quebrado — e a reação natural é clicar de novo.
 *
 * Reabilita no `finally`, inclusive quando dá erro: um botão que fica morto
 * depois de uma falha obriga a recarregar a página para tentar de novo.
 */
export async function ocupado(botao, rotulo, tarefa) {
  const grupo = botao.closest(".botoes, .gaveta-botoes") || botao.parentElement;
  const irmaos = [...(grupo?.querySelectorAll("button") || [botao])];
  const original = botao.innerHTML;

  irmaos.forEach((b) => (b.disabled = true));
  botao.dataset.ocupado = "1";

  // O relógio andando é o que diferencia "trabalhando" de "travado". Numa
  // geração de ~60 s com um modelo local, é a única informação honesta que a
  // tela tem: o servidor não sabe dizer "faltam 30%" sem inventar o número.
  const comecou = Date.now();
  const pintar = () => {
    const s = Math.round((Date.now() - comecou) / 1000);
    botao.innerHTML =
      `<i class="girando"></i>${escapar(rotulo)}` +
      (s >= 3 ? `<span class="cronometro">${s}s</span>` : "");
  };
  pintar();
  const relogio = setInterval(pintar, 1000);

  try {
    return await tarefa();
  } finally {
    clearInterval(relogio);
    delete botao.dataset.ocupado;
    botao.innerHTML = original;
    irmaos.forEach((b) => (b.disabled = false));
  }
}
