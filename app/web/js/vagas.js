/* Candidaturas: a tabela e a gaveta lateral.
 *
 * A tabela é a lista; a gaveta é o registro aberto, editável campo a campo —
 * o gesto do Notion, que é o que torna "clicar e digitar" descobrível sem
 * instrução nenhuma.
 */
import { api } from "./api.js";
import * as aviso from "./avisos.js";
import { $, data, escapar, haQuanto, ocupado } from "./ui.js";

// A vaga aberta na gaveta. Guardada inteira porque a gaveta é editável: o
// refresco não pode repintar por baixo de um campo em edição.
let vagaAberta = null;
let vagasEmTela = [];

export const STATUS = {
  quero_candidatar: "quero me candidatar",
  candidatei: "candidatei",
  respondeu: "responderam",
  entrevista: "entrevista",
  fim: "encerrada",
};

export const temGavetaAberta = () => vagaAberta !== null;

// ── a tabela ────────────────────────────────────────────────────

function pintarScore(n) {
  if (n == null) return '<span class="rotulo">—</span>';
  const classe = n >= 70 ? "alto" : n < 45 ? "baixo" : "";
  return `<span class="score ${classe}" title="aderência ao meu perfil">
    <i><b style="width:${Math.max(0, Math.min(100, n))}%"></b></i>${n}</span>`;
}

function pintarTabela(itens) {
  $("vagas-total").textContent = itens.length;
  $("vagas-total").dataset.zero = itens.length ? "0" : "1";

  if (!itens.length) {
    return `<p class="vazio">Nenhuma vaga ainda. Clique em <b>+ colar vaga</b> e cole a descrição.</p>`;
  }

  const linhas = itens
    .map((v) => {
      const local = [v.modelo, v.localizacao].filter(Boolean).join(" · ");
      return `
      <tr data-id="${v.id}" tabindex="0" ${vagaAberta?.id === v.id ? 'aria-selected="true"' : ""}>
        <td class="cel-limitada">
          <div class="vaga-titulo">${escapar(v.titulo)}</div>
          ${local ? `<div class="vaga-sub">${escapar(local)}</div>` : ""}
        </td>
        <td class="cel-limitada">${escapar(v.empresa || "—")}</td>
        <td><span class="pill" data-status="${v.status}">${escapar(STATUS[v.status] || v.status)}</span></td>
        <td class="num">${pintarScore(v.match_score)}</td>
        <td class="esconde-estreito">${
          v.tem_curriculo
            ? `<span class="marca-sim" title="gerado ${haQuanto(v.curriculo_gerado_em)}">✓ pronto</span>`
            : '<span class="marca-nao">—</span>'
        }</td>
        <td class="num esconde-estreito rotulo">${data(v.created_at)}</td>
      </tr>`;
    })
    .join("");

  return `<table class="vagas">
    <thead><tr>
      <th>Vaga</th><th>Empresa</th><th>Status</th><th class="num">Match</th>
      <th class="esconde-estreito">Currículo</th><th class="num esconde-estreito">Colada</th>
    </tr></thead>
    <tbody>${linhas}</tbody>
  </table>`;
}

export async function carregarTabela() {
  const status = $("filtro-status").value;
  const r = await api(`/api/vagas?limite=200${status ? `&status=${status}` : ""}`);
  vagasEmTela = r.itens || [];
  $("tabela-vagas").innerHTML = pintarTabela(vagasEmTela);
}

// ── a gaveta ────────────────────────────────────────────────────

function campo(rotulo, nome, valor, vazio = "vazio") {
  return `<span class="rot">${rotulo}</span>
    <div data-campo="${nome}" contenteditable="plaintext-only" spellcheck="false"
         data-vazio="${vazio}">${escapar(valor || "")}</div>`;
}

function pintarGaveta(v) {
  const req = v.analise_json || {};
  const m = v.match_json || {};
  const cur = v.curriculo_json || {};

  const listaTags = (itens, prefixo = "") =>
    (itens || []).length
      ? `<div class="tags">${itens.map((x) => `<span class="tag">${prefixo}${escapar(x)}</span>`).join("")}</div>`
      : '<p class="vazio">—</p>';

  const opcoesStatus = Object.entries(STATUS)
    .map(([k, r]) => `<option value="${k}" ${v.status === k ? "selected" : ""}>${r}</option>`)
    .join("");

  const analise = v.analise_json
    ? `
    <div class="gaveta-secao">
      <h3>Análise da vaga</h3>
      <div class="linha sutil"><span>aderência</span><span>${v.match_score ?? "—"}/100</span></div>
      <div class="rotulo" style="margin-top:10px">requisitos obrigatórios</div>
      ${listaTags(req.obrigatorios)}
      <div class="rotulo" style="margin-top:10px">o que eu já tenho</div>
      ${listaTags(m.destaques, "✓ ")}
      <div class="rotulo" style="margin-top:10px">o que falta (estudar)</div>
      ${listaTags(m.gaps, "· ")}
    </div>`
    : `<div class="gaveta-secao"><h3>Análise da vaga</h3>
        <p class="vazio">Ainda não analisada — use o botão acima.</p></div>`;

  const curriculo = v.curriculo_gerado_em
    ? `
    <div class="gaveta-secao">
      <h3>Currículo</h3>
      <div class="linha sutil"><span>gerado</span><span>${haQuanto(v.curriculo_gerado_em)}</span></div>
      <div class="linha sutil"><span>título</span><span>${escapar(cur.titulo || "—")}</span></div>
      ${(cur.avisos || []).map((a) => `<div class="acao"><div class="aviso">⚠ ${escapar(a)}</div></div>`).join("")}
      ${
        (cur.rejeitados || []).length
          ? `<div class="rotulo" style="margin-top:8px">a anti-alucinação derrubou</div>
             ${listaTags(cur.rejeitados)}`
          : '<p class="rotulo" style="margin-top:8px">nada rejeitado pela anti-alucinação ✓</p>'
      }
    </div>`
    : "";

  const historico = (v.historico || []).length
    ? `<div class="timeline">${v.historico
        .slice()
        .reverse()
        .map(
          (e) => `<div class="ev"><b>${escapar(e.evento)}</b>
            <span class="quando">${haQuanto(e.ocorreu_em)}</span>
            ${e.detalhe ? `<div>${escapar(e.detalhe)}</div>` : ""}</div>`
        )
        .join("")}</div>`
    : '<p class="vazio">sem eventos</p>';

  return `
    <div class="gaveta-secao">
      <div class="campos">
        <span class="rot">empresa</span>
        <div data-campo="empresa" contenteditable="plaintext-only" spellcheck="false"
             data-vazio="qual empresa?">${escapar(v.empresa || "")}</div>
        <span class="rot">status</span>
        <div><select data-campo-select="status">${opcoesStatus}</select></div>
        ${campo("senioridade", "senioridade", v.senioridade, "júnior / pleno / sênior")}
        ${campo("modelo", "modelo", v.modelo, "remoto / híbrido / presencial")}
        ${campo("localização", "localizacao", v.localizacao, "cidade")}
        ${campo("link", "link", v.link, "url da vaga")}
        ${campo("fonte", "fonte", v.fonte, "LinkedIn, indicação…")}
        ${campo("contato", "contato_email", v.contato_email, "e-mail do recrutador")}
      </div>
      <div class="gaveta-botoes">
        <button data-fluxo="analisar">analisar</button>
        <button data-fluxo="gerar" class="primario">analisar + gerar</button>
        ${
          v.curriculo_gerado_em
            ? `<a class="botao-link" href="/api/vagas/${v.id}/curriculo.pdf" target="_blank" rel="noopener">ver PDF</a>`
            : ""
        }
        <button data-acao="apagar" class="perigo" title="apaga a vaga e o histórico">apagar</button>
      </div>
    </div>

    ${analise}
    ${curriculo}

    <div class="gaveta-secao">
      <h3>Minhas notas</h3>
      <div data-campo="notas" contenteditable="plaintext-only"
           data-vazio="o que lembrar sobre esta vaga…">${escapar(v.notas || "")}</div>
    </div>

    <div class="gaveta-secao">
      <h3>Descrição colada</h3>
      <div class="descricao-vaga" data-campo="descricao" contenteditable="plaintext-only"
           data-vazio="vazio">${escapar(v.descricao || "")}</div>
    </div>

    <div class="gaveta-secao">
      <h3>Histórico</h3>
      ${historico}
    </div>`;
}

export async function abrirGaveta(id) {
  // Busca o detalhe (traz descrição e histórico, que a listagem não traz).
  vagaAberta = await api(`/api/vagas/${id}`);
  $("gaveta-titulo").textContent = vagaAberta.titulo;
  $("gaveta-etiqueta").textContent = vagaAberta.empresa || "Vaga";
  $("gaveta-corpo").innerHTML = pintarGaveta(vagaAberta);
  $("gaveta").hidden = false;
  $("gaveta-fundo").hidden = false;
  // Rolagem da página congelada: rolar o fundo com a gaveta aberta perde o
  // lugar da lista, que é justamente para onde eu volto ao fechar.
  document.body.style.overflow = "hidden";
  $("tabela-vagas").innerHTML = pintarTabela(vagasEmTela);
}

export function fecharGaveta() {
  vagaAberta = null;
  $("gaveta").hidden = true;
  $("gaveta-fundo").hidden = true;
  document.body.style.overflow = "";
  $("tabela-vagas").innerHTML = pintarTabela(vagasEmTela);
}

/** Salva um campo e devolve `true` se deu certo. */
async function salvarCampo(elemento, nome, valor) {
  if (!vagaAberta) return false;
  if ((vagaAberta[nome] || "") === valor) return true; // nada mudou

  elemento.dataset.salvando = "1";
  try {
    const atualizada = await api(`/api/vagas/${vagaAberta.id}`, {
      method: "PATCH",
      body: JSON.stringify({ [nome]: valor || null }),
    });
    Object.assign(vagaAberta, atualizada);
    delete elemento.dataset.salvando;
    elemento.dataset.salvo = "1";
    setTimeout(() => delete elemento.dataset.salvo, 900);
    await carregarTabela();
    return true;
  } catch (erro) {
    delete elemento.dataset.salvando;
    // Volta o que estava: um campo que "aceitou" um valor que o servidor
    // recusou é a pior mentira que uma tela pode contar.
    if (elemento.tagName === "SELECT") elemento.value = vagaAberta[nome];
    else elemento.textContent = vagaAberta[nome] || "";
    aviso.erro("Não salvou", { detalhe: erro.message });
    return false;
  }
}

// ── analisar / gerar ────────────────────────────────────────────

/**
 * O caminho de `analisar` e de `analisar + gerar`, que só diferem no fim.
 *
 * O resultado **nunca termina no vácuo**: se eu fechar a gaveta no meio de uma
 * geração de 60 s, a operação continua e o desfecho vira um aviso com link para
 * o PDF. Antes, o handler tentava repintar uma gaveta que não existia mais e
 * escrevia o erro num elemento escondido — o currículo era gerado e eu não
 * ficava sabendo.
 */
async function rodarFluxo(vagaId, fluxo, botao) {
  const rotulo = fluxo === "gerar" ? "gerando… (~1 min)" : "analisando…";
  const eraAberta = vagaAberta?.id === vagaId;

  try {
    const r = await ocupado(botao, rotulo, () =>
      fluxo === "gerar"
        ? // Uma chamada só: o servidor reanalisa e gera, e devolve a vaga junto.
          api(`/api/vagas/${vagaId}/curriculo?reanalisar=true`, { method: "POST" })
        : api(`/api/vagas/${vagaId}/analisar?forcar=true`, { method: "POST" })
    );

    await carregarTabela();

    if (vagaAberta?.id === vagaId) {
      await abrirGaveta(vagaId); // repinta com análise/currículo novos
    } else if (eraAberta) {
      // Fechei no meio: o aviso é o único lugar onde o resultado ainda aparece.
      const nome = r?.vaga?.titulo || r?.titulo || "a vaga";
      aviso.ok(
        fluxo === "gerar" ? `Currículo de ${nome} pronto` : `${nome} analisada`,
        fluxo === "gerar"
          ? { acao: "ver PDF", href: `/api/vagas/${vagaId}/curriculo.pdf` }
          : { acao: "abrir", aoClicar: () => abrirGaveta(vagaId) }
      );
    }
    return r;
  } catch (erro) {
    aviso.erro(fluxo === "gerar" ? "Falhou ao gerar" : "Falhou ao analisar", {
      detalhe: erro.message,
    });
    throw erro;
  }
}

async function apagarVaga(id, titulo) {
  const certeza = await aviso.confirmar(`Apagar “${titulo}”?`, {
    descricao: "O histórico da candidatura vai junto. Não dá para desfazer.",
    confirmar: "apagar",
  });
  if (!certeza) return;

  try {
    await api(`/api/vagas/${id}`, { method: "DELETE" });
    fecharGaveta();
    await carregarTabela();
    aviso.ok("Vaga apagada");
  } catch (erro) {
    aviso.erro("Não consegui apagar", { detalhe: erro.message });
  }
}

// ── ligação dos eventos ─────────────────────────────────────────

export function ligar() {
  // Salvar ao sair do campo é o gesto do Notion: clico fora e está salvo.
  document.addEventListener(
    "blur",
    (e) => {
      const alvo = e.target.closest?.("[data-campo]");
      if (!alvo || !vagaAberta) return;
      salvarCampo(alvo, alvo.dataset.campo, alvo.textContent.trim());
    },
    true
  );

  document.addEventListener("keydown", (e) => {
    const alvo = e.target.closest?.("[data-campo]");
    if (alvo && e.key === "Escape") {
      // Esc no campo desfaz a edição; só depois Esc fecha a gaveta.
      alvo.textContent = vagaAberta?.[alvo.dataset.campo] || "";
      alvo.blur();
      e.stopPropagation();
      return;
    }
    // Enter salva em campo de uma linha; na descrição e nas notas quebra linha.
    if (alvo && e.key === "Enter" && !["descricao", "notas"].includes(alvo.dataset.campo)) {
      e.preventDefault();
      alvo.blur();
      return;
    }
    if (e.key === "Escape" && !$("gaveta").hidden) fecharGaveta();
  });

  $("gaveta-fechar").addEventListener("click", fecharGaveta);
  $("gaveta-fundo").addEventListener("click", fecharGaveta);

  $("gaveta-corpo").addEventListener("change", async (e) => {
    const select = e.target.closest("[data-campo-select]");
    if (select) await salvarCampo(select, select.dataset.campoSelect, select.value);
  });

  $("gaveta-corpo").addEventListener("click", async (e) => {
    if (!vagaAberta) return;
    const apagar = e.target.closest('button[data-acao="apagar"]');
    if (apagar) return apagarVaga(vagaAberta.id, vagaAberta.titulo);

    const botao = e.target.closest("button[data-fluxo]");
    if (botao) await rodarFluxo(vagaAberta.id, botao.dataset.fluxo, botao).catch(() => {});
  });

  // Abrir a vaga: clique ou Enter na linha (a linha tem tabindex por isso).
  $("tabela-vagas").addEventListener("click", (e) => {
    const linha = e.target.closest("tr[data-id]");
    if (linha) abrirGaveta(linha.dataset.id).catch((erro) => aviso.erro(erro.message));
  });
  $("tabela-vagas").addEventListener("keydown", (e) => {
    const linha = e.target.closest("tr[data-id]");
    if (linha && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      abrirGaveta(linha.dataset.id).catch((erro) => aviso.erro(erro.message));
    }
  });

  ligarFormularioNovo();

  $("filtro-status").innerHTML =
    '<option value="">todos os status</option>' +
    Object.entries(STATUS).map(([k, r]) => `<option value="${k}">${r}</option>`).join("");
  $("filtro-status").addEventListener("change", () => carregarTabela().catch(() => {}));
}

// ── colar vaga nova ─────────────────────────────────────────────

function mostrarForm(mostrar) {
  $("form-vaga").hidden = !mostrar;
  $("btn-nova").textContent = mostrar ? "fechar" : "+ colar vaga";
  if (mostrar) $("nova-descricao").focus();
}

function ligarFormularioNovo() {
  $("btn-nova").addEventListener("click", () => mostrarForm($("form-vaga").hidden));
  $("btn-cancelar-vaga").addEventListener("click", () => {
    $("form-vaga").reset();
    mostrarForm(false);
  });

  $("form-vaga").addEventListener("submit", async (e) => {
    e.preventDefault();
    const botao = e.submitter;
    const fluxo = botao?.dataset.fluxo || "salvar";
    const descricao = $("nova-descricao").value.trim();

    if (descricao.length < 50) {
      aviso.erro("Cole a descrição inteira", {
        detalhe: "Precisa de pelo menos 50 caracteres para extrair requisitos.",
      });
      $("nova-descricao").focus();
      return;
    }

    try {
      const vaga = await ocupado(botao, fluxo === "salvar" ? "salvando…" : "salvando…", () =>
        api("/api/vagas", {
          method: "POST",
          body: JSON.stringify({
            descricao,
            titulo: $("nova-titulo").value.trim() || null,
            empresa: $("nova-empresa").value.trim() || null,
            link: $("nova-link").value.trim() || null,
          }),
        })
      );

      $("form-vaga").reset();
      mostrarForm(false);
      await carregarTabela();
      await abrirGaveta(vaga.id); // já abre no que acabou de sair

      if (fluxo !== "salvar") {
        const naGaveta = $("gaveta-corpo").querySelector(`button[data-fluxo="${fluxo}"]`);
        await rodarFluxo(vaga.id, fluxo, naGaveta).catch(() => {});
      } else {
        aviso.ok("Vaga salva");
      }
    } catch (erro) {
      aviso.erro("Não consegui salvar a vaga", { detalhe: erro.message });
    }
  });
}
