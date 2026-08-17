/* Gravar uma aula ou reunião, ver o texto aparecendo, e salvar no vault.
 *
 * ## Por que o texto aparece ao vivo
 *
 * Não é enfeite. É a única forma de eu saber, **antes de perder uma hora de
 * aula**, que a fonte de áudio está errada — gravar o microfone quando eu
 * queria o som do sistema é o erro mais fácil de cometer aqui, e sem retorno na
 * tela ele só apareceria no fim.
 *
 * ## Por que perguntar o nome só no fim
 *
 * Porque no começo eu não sei. Ligo quando o vídeo começa; o assunto de verdade
 * aparece no meio. Pedir o título antes é pedir um chute que eu nunca volto
 * para corrigir — e nome ruim de nota é o que faz a busca não achar depois.
 *
 * O modelo local propõe título, pasta, tags e nome de arquivo lendo a
 * transcrição; a tela só me deixa confirmar ou corrigir.
 */
import { api } from "./api.js";
import * as aviso from "./avisos.js";
import { $, escapar, ocupado } from "./ui.js";

// Um segundo enquanto grava: é o intervalo em que o cronômetro parece contínuo
// e o texto novo (que sai a cada 20 s) aparece sem atraso perceptível.
const PULSO_MS = 1000;

let pulso = null;
let ultimoEstado = "ocioso";
let destinos = { pastas: [], tags: [] };

const relogio = (s) =>
  `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** Grava enquanto a aba estiver aberta — mas o estado real mora no servidor. */
function pintar(e) {
  const gravando = e.estado === "gravando";
  const processando = e.estado === "processando";
  const revisando = e.estado === "revisar";

  const botao = $("btn-gravar");
  botao.textContent = gravando ? "■ parar" : "● gravar";
  botao.dataset.gravando = gravando ? "1" : "";
  botao.disabled = processando;
  $("fonte-audio").disabled = gravando || processando || revisando;

  const marcador = $("transcricao-tempo");
  marcador.textContent = gravando
    ? `${relogio(e.segundos)} · ${e.palavras} palavras`
    : processando
      ? "organizando…"
      : "•";
  marcador.dataset.zero = gravando || processando ? "0" : "1";

  $("transcricao-dica").hidden = gravando || processando || revisando;

  const viva = $("transcricao-viva");
  if (gravando || processando || revisando) {
    viva.hidden = false;
    const grudado = viva.scrollHeight - viva.scrollTop - viva.clientHeight < 60;
    viva.innerHTML =
      e.trechos.map(pintarTrecho).join("") ||
      '<p class="vazio">ouvindo… (o primeiro trecho sai em ~20 s)</p>';
    if (processando) {
      viva.innerHTML += '<p class="rotulo">o modelo local está organizando o texto…</p>';
    }
    // Só rola sozinho enquanto grava e se eu já estava no fim: senão, ler o
    // começo (ou revisar) vira briga com a rolagem.
    if (gravando && grudado) viva.scrollTop = viva.scrollHeight;
  } else {
    viva.hidden = true;
    viva.innerHTML = "";
  }

  // O `ultimoEstado` é o que impede o formulário de ser repreenchido a cada
  // segundo: sem ele, o pulso apagaria o título que eu estou digitando. É o
  // mesmo defeito da fila, que apagava o textarea a cada refresco.
  if (revisando && ultimoEstado !== "revisar") preencherFormulario(e);
  $("form-nota").hidden = !revisando;

  ultimoEstado = e.estado;
}

/** Um trecho com o instante do vídeo e o ✕ para cortar anúncio. */
function pintarTrecho(t) {
  return `<p class="trecho" data-indice="${t.indice}" ${t.anuncio ? 'data-anuncio="1"' : ""}>
    <span class="trecho-tempo">${escapar(t.relogio)}</span>
    <span class="trecho-texto">${escapar(t.texto)}</span>
    <button class="trecho-cortar" title="cortar este trecho (anúncio, ruído)">✕</button>
  </p>`;
}

function preencherFormulario(e) {
  const s = e.sugestao || {};
  $("nota-titulo").value = s.titulo || "";
  $("nota-pasta").value = s.pasta || "";
  $("nota-arquivo").value = s.nome_arquivo || "";
  $("nota-tags").value = (s.tags || []).join(", ");
  $("nota-resumo").textContent = s.resumo || "";

  // Busca agora, e não no carregamento da página — ver `ligar()`.
  carregarPastas(s.pasta).catch(() => pintarPastas(s.pasta));

  // Por que esta pasta: as notas que a busca semântica achou parecidas. É a
  // evidência atrás da sugestão — sem isso, "Pessoal/Machine Learning" é um
  // palpite que eu aceito sem conferir.
  const vizinhas = (s.relacionadas || []).length
    ? `<div class="rotulo" style="margin-top:8px">você já tem notas parecidas (a nota vai linkar para elas)</div>
       <div class="tags">${s.relacionadas
         .map((r) => `<span class="tag">${escapar(r.replace(/^\[\[|\]\]$/g, ""))}</span>`)
         .join("")}</div>`
    : `<p class="rotulo" style="margin-top:8px">nenhuma nota parecida no índice — assunto novo</p>`;

  // O que o glossário corrigiu fica à vista: é assim que eu descubro o que
  // acrescentar em data/glossario.json — a transcrição melhora com o uso.
  const corrigidos = (s.corrigidos || []).length
    ? `<div class="rotulo" style="margin-top:8px">o glossário corrigiu</div>
       <div class="tags">${s.corrigidos.map((c) => `<span class="tag">${escapar(c)}</span>`).join("")}</div>`
    : "";

  $("nota-corrigidos").innerHTML = vizinhas + corrigidos;

  // O texto bruto continua à vista para eu conferir, mas sem o "organizando…",
  // que já terminou — deixá-lo faz a tela parecer travada no passo anterior.
  const viva = $("transcricao-viva");
  viva.hidden = false;
  viva.querySelector("p.rotulo")?.remove();

  $("nota-titulo").focus();
  $("nota-titulo").select();
}

/** As pastas do vault, clicáveis. `_inbox` significa "não sei" — e sabendo
 *  disso, a lista tem que estar à vista, não escondida atrás de um datalist. */
const semAcento = (t) =>
  t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

function pintarPastas(escolhida, { filtro = "" } = {}) {
  if (escolhida !== undefined) $("nota-pasta").value = escolhida || "";
  $("pastas-do-vault").innerHTML = destinos.pastas
    .map((p) => `<option value="${escapar(p)}">`)
    .join("");

  const atual = $("nota-pasta").value.trim();
  const inbox = !atual || atual === "_inbox";
  // Com 38 pastas, achar a certa exige rolar — a menos que digitar filtre.
  // "matem" tem que achar "Matemática" mesmo eu não pondo o acento.
  const alvo = semAcento(filtro.trim());
  const visiveis = alvo
    ? destinos.pastas.filter((p) => semAcento(p).includes(alvo))
    : destinos.pastas;

  const chips = visiveis
    .map(
      (p) =>
        `<button type="button" class="pasta-chip" data-pasta="${escapar(p)}"
           ${p === atual ? 'aria-pressed="true"' : ""}>${escapar(p)}</button>`
    )
    .join("");

  $("pastas-sugeridas").innerHTML =
    (inbox
      ? '<span class="rotulo aviso-inbox">nenhuma nota parecida — escolha a pasta:</span>'
      : "") +
    (chips ||
      `<span class="rotulo">nenhuma pasta com “${escapar(filtro)}” — ` +
        "ela será criada ao salvar</span>");
}

async function carregarPastas(escolhida) {
  try {
    destinos = await api("/api/transcricao/destinos");
  } catch {
    /* segue com a lista que já tem */
  }
  pintarPastas(escolhida ?? $("nota-pasta").value);
}

async function consultar() {
  try {
    pintar(await api("/api/transcricao/estado"));
  } catch {
    /* sessão expirada já é tratada no api.js */
  }
}

/** Liga e desliga o pulso. Sempre limpa antes: dois `setInterval` vivos ao
 *  mesmo tempo dobrariam as requisições e nunca mais dariam para desligar. */
function pulsar(ligado) {
  clearInterval(pulso);
  if (ligado) pulso = setInterval(consultar, PULSO_MS);
}

export function ligar() {
  $("btn-gravar").addEventListener("click", async (ev) => {
    const botao = ev.currentTarget;
    const gravando = botao.dataset.gravando === "1";
    try {
      if (gravando) {
        const e = await ocupado(botao, "finalizando…", () =>
          api("/api/transcricao/parar", { method: "POST" })
        );
        pintar(e);
        pulsar(true); // continua consultando: o LLM organiza em segundo plano
      } else {
        const e = await ocupado(botao, "iniciando…", () =>
          api("/api/transcricao/iniciar", {
            method: "POST",
            body: JSON.stringify({ fonte: $("fonte-audio").value }),
          })
        );
        pintar(e);
        pulsar(true);
        aviso.ok("Gravando — pode dar play", {
          detalhe: "O texto aparece aqui a cada 20 segundos.",
        });
      }
    } catch (erro) {
      aviso.erro(gravando ? "Não consegui finalizar" : "Não consegui gravar", {
        detalhe: erro.message,
      });
      await consultar();
    }
  });

  $("form-nota").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const botao = ev.submitter;
    try {
      const r = await ocupado(botao, "salvando e indexando…", () =>
        api("/api/transcricao/salvar", {
          method: "POST",
          body: JSON.stringify({
            titulo: $("nota-titulo").value.trim(),
            pasta: $("nota-pasta").value.trim(),
            nome_arquivo: $("nota-arquivo").value.trim() || null,
            tags: $("nota-tags").value.split(",").map((t) => t.trim()).filter(Boolean),
          }),
        })
      );
      pulsar(false);
      await consultar();
      aviso.ok("Nota salva no Second Brain", {
        detalhe: `${r.caminho.split("/").slice(-2).join("/")} · ${r.chunks} chunks indexados`,
      });
    } catch (erro) {
      aviso.erro("Não consegui salvar a nota", { detalhe: erro.message });
    }
  });

  $("btn-descartar").addEventListener("click", async () => {
    const certeza = await aviso.confirmar("Descartar a transcrição?", {
      descricao: "O texto não foi salvo em lugar nenhum. Não dá para desfazer.",
      confirmar: "descartar",
    });
    if (!certeza) return;
    await api("/api/transcricao/descartar", { method: "POST" }).catch(() => {});
    pulsar(false);
    await consultar();
  });

  // Cortar um trecho: o anúncio que começou antes de eu pular o vídeo.
  $("transcricao-viva").addEventListener("click", async (ev) => {
    const botao = ev.target.closest(".trecho-cortar");
    if (!botao) return;
    const trecho = botao.closest(".trecho");
    trecho.dataset.saindo = "1";
    try {
      pintar(await api(`/api/transcricao/trecho/${trecho.dataset.indice}`, { method: "DELETE" }));
    } catch (erro) {
      delete trecho.dataset.saindo;
      aviso.erro("Não consegui cortar o trecho", { detalhe: erro.message });
    }
  });

  $("pastas-sugeridas").addEventListener("click", (ev) => {
    const chip = ev.target.closest(".pasta-chip");
    if (chip) pintarPastas(chip.dataset.pasta);
  });

  $("btn-recarregar-pastas").addEventListener("click", async (ev) => {
    await ocupado(ev.currentTarget, "lendo…", () => carregarPastas());
  });

  // Digitar filtra a lista; e digitar uma pasta que não existe é legítimo —
  // ela é criada ao salvar.
  $("nota-pasta").addEventListener("input", (ev) =>
    pintarPastas(undefined, { filtro: ev.target.value })
  );

  // A lista de pastas NÃO é buscada aqui: `ligar()` roda antes de `iniciar()`,
  // ou seja antes do login, e a chamada tomava 401 — o seletor nascia vazio e a
  // nota ia para o `_inbox` mesmo existindo a pasta certa. Ela é buscada ao
  // entrar em `revisar`, e de novo no botão `↻ pastas` (criar pasta no Obsidian
  // no meio da aula é o caso comum).

  // Se eu recarregar a aba no meio de uma gravação, a tela reencontra a sessão:
  // ela vive no servidor, não aqui.
  consultar().then(() => {
    if (["gravando", "processando"].includes(ultimoEstado)) pulsar(true);
  });
}

/** Uma gravação em andamento não pode ser perdida por fechar a aba sem querer. */
export const gravando = () => ultimoEstado === "gravando";
