/* A casca que as duas páginas compartilham: login, sessão e o ciclo de refresco.
 *
 * ## Por que existe
 *
 * As candidaturas saíram para `/candidaturas/` porque a lista fica poluída
 * assim que passam de uma dúzia. Duas páginas de verdade resolvem isso — e
 * trazem o risco clássico: o mesmo login e o mesmo timer escritos duas vezes,
 * que divergem no primeiro conserto feito só de um lado.
 *
 * Então o HTML de cada página tem só o que é dela, e tudo que é igual mora
 * aqui — **inclusive o formulário de login**, que é injetado por JS. Ele nasce
 * escondido e só aparece depois que `/api/auth/me` falha, então não há risco de
 * piscar na tela antes do JS decidir.
 *
 * A sessão é a mesma nas duas páginas (cookie), então navegar de uma para a
 * outra não pede senha de novo.
 *
 * ## O que a gravação tem a ver com isso
 *
 * Nada, e é isso que torna duas páginas viável: quem grava é o **servidor**
 * (ffmpeg), não o navegador. Sair de `/` no meio de uma aula não interrompe a
 * gravação — a outra página lê `/api/transcricao/estado` e mostra o mesmo
 * andamento. Se a gravação fosse do lado do cliente, uma navegação real perderia
 * a aula, e a resposta certa seria abas em vez de páginas.
 */
import { api, quandoExpirar } from "./api.js";
import { $, REFRESCO_MS } from "./ui.js";

const LOGIN_HTML = `
  <form id="form-login">
    <h1>Copiloto</h1>
    <p class="sub">assistente pessoal local-first</p>
    <input type="email" id="email" placeholder="e-mail" autocomplete="username" required>
    <input type="password" id="senha" placeholder="senha" autocomplete="current-password" required>
    <button type="submit">entrar</button>
    <p class="erro" id="erro-login" hidden></p>
  </form>`;

let timer = null;
let carregarPagina = async () => {};

function mostrarLogin() {
  clearInterval(timer);
  $("painel").hidden = true;
  $("login").hidden = false;
  $("email")?.focus();
}

async function iniciar() {
  try {
    await api("/api/auth/me");
  } catch {
    return mostrarLogin();
  }
  $("login").hidden = true;
  $("painel").hidden = false;
  await carregarPagina();
  clearInterval(timer);
  timer = setInterval(() => carregarPagina().catch(() => {}), REFRESCO_MS);
}

/**
 * Liga login, sessão e refresco.
 *
 * @param {() => Promise<void>} carregar  o que esta página busca e pinta.
 * @param {() => boolean} [segurar]  `true` enquanto houver edição na tela: o
 *   `beforeunload` avisa antes de fechar a aba. Fechar no meio de uma edição é
 *   o mesmo dado perdido pela outra porta.
 */
export function ligar(carregar, segurar = () => false) {
  carregarPagina = carregar;
  $("login").innerHTML = LOGIN_HTML;
  quandoExpirar(mostrarLogin);

  $("form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("erro-login").hidden = true;
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: $("email").value, senha: $("senha").value }),
      });
      $("senha").value = "";
      iniciar();
    } catch (erro) {
      $("erro-login").textContent =
        erro.message === "erro 401" ? "e-mail ou senha errados" : erro.message;
      $("erro-login").hidden = false;
    }
  });

  $("sair").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" }).catch(() => {});
    mostrarLogin();
  });

  // Aba escondida não precisa de dado fresco — e o refresco acorda a GPU à toa.
  document.addEventListener("visibilitychange", () => {
    clearInterval(timer);
    if (!document.hidden && !$("painel").hidden) {
      carregarPagina().catch(() => {});
      timer = setInterval(() => carregarPagina().catch(() => {}), REFRESCO_MS);
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if (segurar()) e.preventDefault();
  });

  iniciar();
}

/** O botão ↻ do cabeçalho, igual nas duas páginas. */
export function ligarAtualizar(aoFalhar) {
  $("atualizar").addEventListener("click", async (e) => {
    const botao = e.currentTarget;
    botao.disabled = true;
    botao.dataset.ocupado = "1";
    try {
      await carregarPagina();
    } catch (erro) {
      aoFalhar(erro);
    } finally {
      botao.disabled = false;
      delete botao.dataset.ocupado;
    }
  });
}
