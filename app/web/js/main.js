/* O painel: perguntar, transcrever, fila, conhecimento e modelo.
 *
 * As candidaturas saíram daqui em 20/08/2026 e viraram `/candidaturas/` —
 * a tabela ia ficar ilegível dividindo a tela com o resto assim que as vagas
 * passassem de uma dúzia. O que sobrou nesta página tem uma coisa em comum:
 * é o que eu olho **enquanto** faço outra coisa (uma aula rodando, uma fila
 * para aprovar), e não o que eu abro para trabalhar.
 *
 * A casca (login, sessão, refresco, ↻) mora no `sessao.js`, igual à da outra
 * página.
 */
import { api } from "./api.js";
import * as aviso from "./avisos.js";
import * as blocos from "./blocos.js";
import * as fila from "./fila.js";
import * as sessao from "./sessao.js";
import * as transcricao from "./transcricao.js";
import { $, arquivo, escapar } from "./ui.js";

// `candidaturas` fica de fora: o funil mora na outra página, e buscá-lo aqui
// seria consulta ao banco a cada 15 s sem ninguém para ler.
const BLOCOS = "saude,fila,conhecimento,modelo";

async function carregar() {
  const dados = await api(`/api/painel?blocos=${BLOCOS}`);
  $("saude").innerHTML = blocos.pintarSaude(dados.saude || {}, dados.acoes_decididas_hoje);
  fila.repintar(dados.fila || {});
  $("conhecimento").innerHTML = blocos.pintarConhecimento(dados.conhecimento || {});
  $("modelo").innerHTML = blocos.pintarModelo(dados.modelo || {});
  $("rodape").textContent =
    `${dados.usuario?.email || ""} · atualizado ${new Date().toLocaleTimeString("pt-BR")}`;
}

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

fila.ligar(carregar);
transcricao.ligar();
sessao.ligarAtualizar((erro) => aviso.erro("Não consegui atualizar", { detalhe: erro.message }));
sessao.ligar(carregar, () => fila.emEdicao() || transcricao.gravando());
