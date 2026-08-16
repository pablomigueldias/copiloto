/* Painel do Copiloto — JS puro, sem build.
 *
 * Três responsabilidades: autenticar na mesma sessão do resto do sistema,
 * buscar `/api/painel` de tempos em tempos e pintar. Mutação (aprovar,
 * rejeitar) reenvia o cookie CSRF no header, como o front em Next.js faria.
 */

const REFRESCO_MS = 15_000;
const $ = (id) => document.getElementById(id);

let timer = null;

// ── infraestrutura ──────────────────────────────────────────────

function csrf() {
  // O cookie CSRF é legível de propósito (double-submit): o servidor exige
  // header == cookie, e só quem está na mesma origem consegue ler.
  const nome = document.cookie.includes("__Host-csrf") ? "__Host-csrf" : "csrf_token";
  const achado = document.cookie.split("; ").find((c) => c.startsWith(nome + "="));
  return achado ? decodeURIComponent(achado.split("=")[1]) : "";
}

async function api(caminho, opcoes = {}) {
  const metodo = (opcoes.method || "GET").toUpperCase();
  const cabecalhos = { ...(opcoes.headers || {}) };
  if (metodo !== "GET") {
    cabecalhos["Content-Type"] = "application/json";
    cabecalhos["X-CSRF-Token"] = csrf();
  }
  const r = await fetch(caminho, { ...opcoes, headers: cabecalhos, credentials: "same-origin" });
  if (r.status === 401) {
    mostrarLogin();
    throw new Error("sessão expirada");
  }
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}));
    throw new Error(corpo.detail || `${r.status}`);
  }
  return r.json();
}

const escapar = (t) =>
  String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function haQuanto(iso) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 90) return "agora";
  if (s < 3600) return `há ${Math.round(s / 60)} min`;
  if (s < 86400) return `há ${Math.round(s / 3600)} h`;
  return `há ${Math.round(s / 86400)} d`;
}

const arquivo = (caminho) => String(caminho || "").split("/").pop();

// ── login ───────────────────────────────────────────────────────

function mostrarLogin() {
  clearInterval(timer);
  $("painel").hidden = true;
  $("login").hidden = false;
  $("email").focus();
}

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
    $("erro-login").textContent = erro.message === "401" ? "e-mail ou senha errados" : erro.message;
    $("erro-login").hidden = false;
  }
});

$("sair").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" }).catch(() => {});
  mostrarLogin();
});

$("atualizar").addEventListener("click", () => carregar());

// ── pintar ──────────────────────────────────────────────────────

function pintarSaude(s, decididas) {
  if (s.erro) return `<span class="falhou">${escapar(s.erro)}</span>`;
  const ollama = s.ollama
    ? '<span><i class="ponto on"></i>Ollama</span>'
    : '<span><i class="ponto off"></i>Ollama fora</span>';
  return `
    ${ollama}
    <span>índice <b>${haQuanto(s.ultima_varredura)}</b></span>
    <span>decididas hoje <b>${decididas ?? 0}</b></span>`;
}

function pintarFila(f) {
  $("fila-total").textContent = f.pendentes ?? 0;
  $("fila-total").dataset.zero = f.pendentes ? "0" : "1";
  if (f.erro) return `<p class="falhou">${escapar(f.erro)}</p>`;
  if (!f.itens.length) {
    const decididas = Object.entries(f.por_status || {})
      .map(([s, n]) => `${n} ${s}`)
      .join(" · ");
    return `<p class="vazio">Nada esperando decisão.</p>${
      decididas ? `<p class="rotulo">${escapar(decididas)}</p>` : ""
    }`;
  }

  return f.itens
    .map((a) => {
      const avisos = (a.payload?.avisos || []).map((x) => `<div class="aviso">⚠ ${escapar(x)}</div>`).join("");
      const rejeitados = (a.payload?.rejeitados || []).length;
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
          <span class="meta" style="margin-left:auto;align-self:center">${haQuanto(a.criada_em)}</span>
        </div>
      </article>`;
    })
    .join("");
}

function pintarCandidaturas(c) {
  if (c.erro) return `<p class="falhou">${escapar(c.erro)}</p>`;

  const etapas = Object.entries(c.funil || {});
  const maior = Math.max(1, ...etapas.map(([, n]) => n));
  const funil = etapas
    .map(
      ([etapa, n]) => `
      <div class="funil-linha">
        <span>${escapar(etapa)}</span>
        <span class="barra"><i style="width:${(100 * n) / maior}%"></i></span>
        <span class="n">${n}</span>
      </div>`
    )
    .join("");

  const numeros = [
    c.taxa_resposta != null ? ["taxa de resposta", `${c.taxa_resposta}%`] : null,
    c.dias_ate_resposta != null ? ["dias até responder", c.dias_ate_resposta] : null,
    c.score_medio != null ? ["match médio", `${c.score_medio}/100`] : null,
    ["follow-up vencido", c.followup_vencido ?? 0],
  ]
    .filter(Boolean)
    .map(([r, v]) => `<div class="linha sutil"><span>${r}</span><span>${v}</span></div>`)
    .join("");

  const gaps = (c.gaps_frequentes || []).length
    ? `<div class="rotulo" style="margin-top:12px">o que estudar</div>
       <div class="tags">${c.gaps_frequentes
         .map((g) => `<span class="tag"><b>${g.vezes}×</b> ${escapar(g.requisito)}</span>`)
         .join("")}</div>`
    : "";

  const total = Object.values(c.por_status || {}).reduce((a, b) => a + b, 0);
  if (!total) return '<p class="vazio">Nenhuma vaga ainda. <code>scripts/vaga.py --colar</code></p>';

  return `<div class="funil">${funil}</div>${numeros}${gaps}`;
}

function pintarConhecimento(k) {
  if (k.erro) return `<p class="falhou">${escapar(k.erro)}</p>`;
  const chunks = Object.values(k.chunks_por_tipo || {}).reduce((a, b) => a + b, 0);
  const tipos = Object.entries(k.chunks_por_tipo || {})
    .map(([t, n]) => `<span class="tag"><b>${n}</b> ${escapar(t)}</span>`)
    .join("");
  const recentes = (k.recentes || [])
    .map(
      (f) => `<div class="item"><span class="ref">${escapar(f.titulo || arquivo(f.fonte_ref))}</span>
              <span class="n">${f.chunks}</span></div>`
    )
    .join("");

  return `
    <div class="numerao">${chunks.toLocaleString("pt-BR")}</div>
    <div class="rotulo">chunks em ${k.fontes} fontes</div>
    <div class="tags">${tipos}</div>
    <div class="rotulo" style="margin-top:12px">indexado por último</div>
    <div class="lista">${recentes || '<p class="vazio">nada ainda</p>'}</div>`;
}

function pintarModelo(m) {
  if (m.erro) return `<p class="falhou">${escapar(m.erro)}</p>`;
  const ultimas = (m.ultimas || [])
    .map(
      (c) => `<div class="item">
        <span class="ref">${c.sucesso ? "✓" : "✗"} ${escapar(c.tarefa || c.agente)}</span>
        <span class="n">${c.latencia_ms ? (c.latencia_ms / 1000).toFixed(1) + "s" : "—"}</span>
      </div>`
    )
    .join("");

  return `
    <div class="numerao">${m.chamadas_24h}</div>
    <div class="rotulo">chamadas em 24 h${m.falhas_24h ? ` · ${m.falhas_24h} falharam` : ""}</div>
    <div class="linha sutil"><span>tokens</span><span>${(m.tokens_24h || 0).toLocaleString("pt-BR")}</span></div>
    <div class="linha sutil"><span>latência média</span><span>${
      m.latencia_media_ms ? (m.latencia_media_ms / 1000).toFixed(1) + "s" : "—"
    }</span></div>
    <div class="rotulo" style="margin-top:12px">últimas chamadas</div>
    <div class="lista">${ultimas || '<p class="vazio">nenhuma ainda</p>'}</div>`;
}

// ── ciclo ───────────────────────────────────────────────────────

async function carregar() {
  const dados = await api("/api/painel");
  $("saude").innerHTML = pintarSaude(dados.saude || {}, dados.acoes_decididas_hoje);
  $("fila").innerHTML = pintarFila(dados.fila || {});
  $("candidaturas").innerHTML = pintarCandidaturas(dados.candidaturas || {});
  $("conhecimento").innerHTML = pintarConhecimento(dados.conhecimento || {});
  $("modelo").innerHTML = pintarModelo(dados.modelo || {});
  $("rodape").textContent = `${dados.usuario?.email || ""} · atualizado ${new Date().toLocaleTimeString("pt-BR")}`;
}

// Decidir da tela. O texto do textarea vai junto: se eu mexi, o serviço
// classifica como 'editada' e o par vira dado de treino.
$("fila").addEventListener("click", async (e) => {
  const botao = e.target.closest("button[data-acao]");
  if (!botao) return;

  const cartao = botao.closest(".acao");
  const decisao = botao.dataset.acao;
  const corpo = { decisao };

  if (decisao === "rejeitar") {
    const motivo = prompt("Por que rejeitar? (o motivo vira sinal de treino)");
    if (motivo === null) return;
    corpo.motivo = motivo;
  } else {
    corpo.texto_final = cartao.querySelector("[data-campo=texto]").value;
  }

  cartao.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    await api(`/api/fila/${cartao.dataset.id}/decidir`, {
      method: "POST",
      body: JSON.stringify(corpo),
    });
    await carregar();
  } catch (erro) {
    alert(erro.message);
    cartao.querySelectorAll("button").forEach((b) => (b.disabled = false));
  }
});

// Perguntar ao conhecimento — a F3 com botão.
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

// Aba escondida não precisa de dado fresco — e o refresco acorda a GPU à toa.
document.addEventListener("visibilitychange", () => {
  clearInterval(timer);
  if (!document.hidden && !$("painel").hidden) {
    carregar().catch(() => {});
    timer = setInterval(() => carregar().catch(() => {}), REFRESCO_MS);
  }
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

iniciar();
