/* Os cartões de leitura do painel: saúde, funil, conhecimento e modelo.
 *
 * Só pintam — nenhum deles tem estado nem manda requisição. Ficam juntos porque
 * mudam pelo mesmo motivo (o formato de `/api/painel`) e nenhum passa de 40
 * linhas sozinho.
 */
import { arquivo, escapar, haQuanto } from "./ui.js";

export function pintarSaude(s, decididas) {
  if (s.erro) return `<span class="falhou">${escapar(s.erro)}</span>`;

  const ollama = s.ollama
    ? '<span><i class="ponto on"></i>Ollama</span>'
    : '<span title="./scripts/copiloto.sh up"><i class="ponto off"></i>Ollama fora</span>';

  // O ponto que faltava. Sem ele, o worker parado é invisível — e índice velho
  // não parece defeito, parece busca ruim. Foi o que escondeu 42 PDFs por 14 h.
  const worker = s.worker
    ? `<span title="último sinal ${haQuanto(s.worker_visto_em)}"><i class="ponto on"></i>worker</span>`
    : '<span class="alerta" title="ninguém está reindexando: ./scripts/copiloto.sh up">' +
      '<i class="ponto off"></i>worker parado</span>';

  return `
    ${ollama}
    ${worker}
    <span>índice <b>${haQuanto(s.ultima_varredura)}</b></span>
    <span>decididas hoje <b>${decididas ?? 0}</b></span>`;
}

export function pintarCandidaturas(c) {
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

export function pintarConhecimento(k) {
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

export function pintarModelo(m) {
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
