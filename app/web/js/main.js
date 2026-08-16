/* Liga os módulos e toca o ciclo do painel.
 *
 * Três responsabilidades, as mesmas do `painel.js` de antes: autenticar na
 * mesma sessão do resto do sistema, buscar `/api/painel` de tempos em tempos, e
 * distribuir o resultado para quem pinta.
 */
import { api, quandoExpirar } from "./api.js";
import * as aviso from "./avisos.js";
import * as blocos from "./blocos.js";
import * as fila from "./fila.js";
import * as transcricao from "./transcricao.js";
import { $, REFRESCO_MS, arquivo, escapar } from "./ui.js";
import * as vagas from "./vagas.js";

let timer = null;

// ── login ───────────────────────────────────────────────────────

function mostrarLogin() {
  clearInterval(timer);
  $("painel").hidden = true;
  $("login").hidden = false;
  $("email").focus();
}

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

// ── ciclo ───────────────────────────────────────────────────────

async function carregar() {
  const dados = await api("/api/painel");
  $("saude").innerHTML = blocos.pintarSaude(dados.saude || {}, dados.acoes_decididas_hoje);
  fila.repintar(dados.fila || {});
  $("candidaturas").innerHTML = blocos.pintarCandidaturas(dados.candidaturas || {});
  $("conhecimento").innerHTML = blocos.pintarConhecimento(dados.conhecimento || {});
  $("modelo").innerHTML = blocos.pintarModelo(dados.modelo || {});
  $("rodape").textContent = `${dados.usuario?.email || ""} · atualizado ${new Date().toLocaleTimeString("pt-BR")}`;

  // A tabela fica fora do refresco quando a gaveta está aberta: repintar por
  // baixo de um campo em edição apagaria o que eu estou digitando.
  if (!vagas.temGavetaAberta()) await vagas.carregarTabela();
}

$("atualizar").addEventListener("click", async (e) => {
  const botao = e.currentTarget;
  botao.disabled = true;
  botao.dataset.ocupado = "1";
  try {
    await carregar();
  } catch (erro) {
    aviso.erro("Não consegui atualizar", { detalhe: erro.message });
  } finally {
    botao.disabled = false;
    delete botao.dataset.ocupado;
  }
});

// ── perguntar ao conhecimento ───────────────────────────────────

$("form-pergunta").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pergunta = $("pergunta").value.trim();
  if (pergunta.length < 3) return;

  const botao = $("btn-perguntar");
  botao.disabled = true;
  botao.textContent = "pensando…";
  $("resposta").hidden = false;
  $("resposta").innerHTML = '<p class="vazio">o modelo local está lendo suas notas…</p>';

  try {
    const r = await api("/api/conhecimento/perguntar", {
      method: "POST",
      body: JSON.stringify({ pergunta }),
    });

    const fontes = (r.fontes || [])
      .map(
        (f) =>
          `<div>· ${escapar(f.titulo || arquivo(f.fonte_ref))}` +
          `<span class="arquivo">${escapar(arquivo(f.fonte_ref))}</span></div>`
      )
      .join("");
    const medida = [
      r.distancia != null ? `distância ${r.distancia.toFixed(3)}` : null,
      r.latencia_ms ? `${(r.latencia_ms / 1000).toFixed(1)}s` : null,
      r.tokens ? `${r.tokens} tokens` : null,
      r.modelo,
    ]
      .filter(Boolean)
      .join(" · ");

    $("resposta").innerHTML = `
      <div class="${r.respondeu ? "texto" : "vazio"}">${escapar(r.texto)}</div>
      ${fontes ? `<div class="fontes">${fontes}</div>` : ""}
      <div class="medida">${escapar(medida)}</div>`;
  } catch (erro) {
    $("resposta").innerHTML = `<p class="falhou">${escapar(erro.message)}</p>`;
  } finally {
    botao.disabled = false;
    botao.textContent = "perguntar";
  }
});

// ── partida ─────────────────────────────────────────────────────

// Aba escondida não precisa de dado fresco — e o refresco acorda a GPU à toa.
document.addEventListener("visibilitychange", () => {
  clearInterval(timer);
  if (!document.hidden && !$("painel").hidden) {
    carregar().catch(() => {});
    timer = setInterval(() => carregar().catch(() => {}), REFRESCO_MS);
  }
});

// Fechar a aba no meio de uma edição é o mesmo dado perdido pela outra porta.
window.addEventListener("beforeunload", (e) => {
  if (fila.emEdicao() || transcricao.gravando()) e.preventDefault();
});

async function iniciar() {
  try {
    await api("/api/auth/me");
  } catch {
    return mostrarLogin();
  }
  $("login").hidden = true;
  $("painel").hidden = false;
  await carregar();
  clearInterval(timer);
  timer = setInterval(() => carregar().catch(() => {}), REFRESCO_MS);
}

fila.ligar(carregar);
vagas.ligar();
transcricao.ligar();
iniciar();
