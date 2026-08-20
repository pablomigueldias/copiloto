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
// O texto do currículo enquanto eu edito. Não-nulo significa "editor aberto", e
// é o que impede a gaveta de repintar por cima do que eu estou escrevendo.
let curriculoEmEdicao = null;
// Quem repinta o resto da página quando a lista muda. O funil sai de
// `/api/painel` e a tabela de `/api/vagas`: sem este aviso, colar uma vaga
// deixava "Candidaturas 1" ao lado de "nenhuma vaga ainda" até o próximo
// ciclo de 15 s. É o defeito que o docstring do `painel.py` existe para
// evitar — a tela mostrando números de dois momentos.
let aoMudar = async () => {};

export const STATUS = {
  quero_candidatar: "quero me candidatar",
  candidatei: "candidatei",
  respondeu: "responderam",
  entrevista: "entrevista",
  fim: "encerrada",
};

export const temGavetaAberta = () => vagaAberta !== null;

// ── busca e ordenação ───────────────────────────────────────────
//
// Tudo no cliente, sobre as ≤200 linhas que a listagem já traz. Filtrar no
// servidor custaria uma ida e volta por tecla digitada para ganhar nada: o
// navegador varre 200 objetos em menos de um milissegundo.
//
// **Paginação não entra.** Ela esconde justamente o que a busca acha, e a
// pergunta que eu faço na tela é "onde está a vaga da Accenture", não "me mostre
// as vagas 21 a 40".

let busca = "";
let ordem = { coluna: "match_score", desc: true };

// Sem acento e minúsculo dos dois lados: eu digito "sao paulo" e a vaga diz
// "São Paulo". Exigir o acento é a busca cobrando precisão que ela deveria dar.
const dobrar = (t) =>
  String(t ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

function filtrar(itens) {
  const alvo = dobrar(busca).trim();
  if (!alvo) return itens;
  // Todos os termos têm que bater, em qualquer campo: "brq dev" acha a vaga de
  // desenvolvedor na BRQ sem eu lembrar a ordem em que escrevi.
  const termos = alvo.split(/\s+/);
  return itens.filter((v) => {
    const feno = dobrar(
      [v.titulo, v.empresa, v.localizacao, v.modelo, v.senioridade, STATUS[v.status]].join(" ")
    );
    return termos.every((t) => feno.includes(t));
  });
}

function ordenar(itens) {
  const { coluna, desc } = ordem;
  const valor = (v) =>
    coluna === "match_score"
      ? v.match_score
      : coluna === "created_at"
        ? v.created_at
        : coluna === "curriculo"
          ? (v.tem_curriculo ? 1 : 0)
          : dobrar(v[coluna]);

  return itens.slice().sort((a, b) => {
    const x = valor(a);
    const y = valor(b);
    // Vaga sem score vai para o fim nos dois sentidos: "sem nota" não é
    // "nota zero", e deixá-la disputar o topo esconde as que têm nota.
    if (x == null || x === "") return 1;
    if (y == null || y === "") return -1;
    if (x === y) return 0;
    return (x > y ? 1 : -1) * (desc ? -1 : 1);
  });
}

// ── a tabela ────────────────────────────────────────────────────

function pintarScore(n) {
  if (n == null) return '<span class="rotulo">—</span>';
  const classe = n >= 70 ? "alto" : n < 45 ? "baixo" : "";
  return `<span class="score ${classe}" title="aderência ao meu perfil">
    <i><b style="width:${Math.max(0, Math.min(100, n))}%"></b></i>${n}</span>`;
}

function pintarTabela(todas) {
  const itens = ordenar(filtrar(todas));
  const filtrado = itens.length !== todas.length;

  // "3 de 12" quando a busca esconde linhas: a badge sozinha mentiria sobre
  // quantas candidaturas eu tenho.
  $("vagas-total").textContent = filtrado ? `${itens.length} de ${todas.length}` : itens.length;
  $("vagas-total").dataset.zero = todas.length ? "0" : "1";
  $("vagas-total").dataset.filtrado = filtrado ? "1" : "0";

  if (!todas.length) {
    return `<p class="vazio">Nenhuma vaga ainda. Clique em <b>+ colar vaga</b> e cole a descrição.</p>`;
  }
  if (!itens.length) {
    return `<p class="vazio">Nada bate com <b>${escapar(busca)}</b>.
      <button class="ghost" data-acao="limpar-busca">limpar busca</button></p>`;
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

  const cab = (rotulo, coluna, classe = "") =>
    `<th class="${classe}" data-ordenar="${coluna}"
         ${ordem.coluna === coluna ? `data-ativa="${ordem.desc ? "desc" : "asc"}"` : ""}
         title="ordenar por ${rotulo.toLowerCase()}" role="button" tabindex="0"
      >${rotulo}</th>`;

  return `<table class="vagas">
    <thead><tr>
      ${cab("Vaga", "titulo")}
      ${cab("Empresa", "empresa")}
      ${cab("Status", "status")}
      ${cab("Match", "match_score", "num")}
      ${cab("Currículo", "curriculo", "esconde-estreito")}
      ${cab("Colada", "created_at", "num esconde-estreito")}
    </tr></thead>
    <tbody>${linhas}</tbody>
  </table>`;
}

/** Repinta a tabela com o que já está em memória — sem ir ao servidor. */
function repintar() {
  $("tabela-vagas").innerHTML = pintarTabela(vagasEmTela);
}

function trocarOrdem(coluna) {
  // Clicar de novo na mesma coluna inverte; coluna nova começa no sentido que
  // interessa: score e data do maior para o menor, texto de A a Z.
  ordem =
    ordem.coluna === coluna
      ? { coluna, desc: !ordem.desc }
      : { coluna, desc: ["match_score", "created_at", "curriculo"].includes(coluna) };
  repintar();
}

export async function carregarTabela() {
  const status = $("filtro-status").value;
  const r = await api(`/api/vagas?limite=200${status ? `&status=${status}` : ""}`);
  vagasEmTela = r.itens || [];
  repintar();
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

  const editor =
    curriculoEmEdicao !== null
      ? `
      <textarea id="curriculo-editor" spellcheck="true"
                aria-label="currículo em texto">${escapar(curriculoEmEdicao)}</textarea>
      <p class="rotulo" style="margin:6px 0 8px">
        O PDF sai deste texto. Seção que eu reescrever de um jeito que o parser
        não reconheça fica como estava — o texto nunca é jogado fora.
      </p>
      <div class="gaveta-botoes">
        <button data-acao="salvar-curriculo" class="primario">salvar e reimprimir</button>
        <button data-acao="cancelar-curriculo">cancelar</button>
      </div>`
      : `<div class="gaveta-botoes" style="margin-top:10px">
          <button data-acao="editar-curriculo">editar currículo</button>
        </div>`;

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
      ${editor}
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
  const antes = vagaAberta?.id;
  vagaAberta = await api(`/api/vagas/${id}`);
  // Trocar de vaga fecha o editor: o texto na tela é de OUTRO currículo, e
  // salvá-lo aqui gravaria o documento errado na vaga errada.
  if (antes !== id) curriculoEmEdicao = null;
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
  curriculoEmEdicao = null;
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

// ── editar o currículo ──────────────────────────────────────────
//
// O texto é a forma de edição, e não um formulário campo a campo, por três
// razões: é o que o `de_texto` do servidor sabe ler, é o que o ATS enxerga, e é
// o mesmo formato que a fila já usava — duas telas editando o mesmo documento
// em formatos diferentes divergiriam no primeiro campo novo.

async function abrirEditor(botao) {
  const id = vagaAberta.id;
  try {
    const r = await ocupado(botao, "abrindo…", () => api(`/api/vagas/${id}/curriculo.txt`));
    if (vagaAberta?.id !== id) return; // fechei a gaveta enquanto carregava
    curriculoEmEdicao = r.texto;
    $("gaveta-corpo").innerHTML = pintarGaveta(vagaAberta);
    const area = $("curriculo-editor");
    area.focus();
    // O cursor no fim, e não no começo: abrir com o texto todo selecionado faz
    // a primeira tecla apagar o currículo inteiro.
    area.setSelectionRange(area.value.length, area.value.length);
  } catch (erro) {
    aviso.erro("Não consegui abrir o currículo", { detalhe: erro.message });
  }
}

function fecharEditor() {
  curriculoEmEdicao = null;
  if (vagaAberta) $("gaveta-corpo").innerHTML = pintarGaveta(vagaAberta);
}

async function salvarCurriculo(botao) {
  const id = vagaAberta.id;
  const texto = $("curriculo-editor").value;

  try {
    const r = await ocupado(botao, "salvando…", () =>
      api(`/api/vagas/${id}/curriculo`, { method: "PUT", body: JSON.stringify({ texto }) })
    );
    curriculoEmEdicao = null;
    await carregarTabela();
    if (vagaAberta?.id === id) await abrirGaveta(id);

    // `pdf: null` é o servidor dizendo que o texto não mudou nada. Avisar
    // "salvo" aí seria mentira pequena, e mentira pequena de tela salvando é
    // exatamente o que faz parar de confiar no aviso.
    aviso.ok(r.pdf ? "Currículo salvo e PDF reimpresso" : "Nada mudou no currículo", {
      acao: "ver PDF",
      href: `/api/vagas/${id}/curriculo.pdf`,
    });
  } catch (erro) {
    // O texto continua na tela: o erro não pode custar o que eu acabei de
    // escrever. Só o aviso aparece.
    aviso.erro("Não consegui salvar", { detalhe: erro.message });
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
    await aoMudar().catch(() => {});

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
    await aoMudar().catch(() => {});
    aviso.ok("Vaga apagada");
  } catch (erro) {
    aviso.erro("Não consegui apagar", { detalhe: erro.message });
  }
}

// ── ligação dos eventos ─────────────────────────────────────────

export function ligar(quandoMudar = async () => {}) {
  aoMudar = quandoMudar;
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
    if (e.key === "Escape" && !$("gaveta").hidden) {
      // Com o editor aberto, Esc não fecha nada: um Esc perdido custaria o
      // currículo inteiro que acabei de reescrever. Sair é pelo "cancelar".
      if (curriculoEmEdicao !== null) return;
      fecharGaveta();
    }
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

    const editar = e.target.closest('button[data-acao="editar-curriculo"]');
    if (editar) return abrirEditor(editar);
    const cancelar = e.target.closest('button[data-acao="cancelar-curriculo"]');
    if (cancelar) return fecharEditor();
    const salvar = e.target.closest('button[data-acao="salvar-curriculo"]');
    if (salvar) return salvarCurriculo(salvar);

    const botao = e.target.closest("button[data-fluxo]");
    if (botao) await rodarFluxo(vagaAberta.id, botao.dataset.fluxo, botao).catch(() => {});
  });

  // Abrir a vaga: clique ou Enter na linha (a linha tem tabindex por isso).
  $("tabela-vagas").addEventListener("click", (e) => {
    const cabecalho = e.target.closest("th[data-ordenar]");
    if (cabecalho) return trocarOrdem(cabecalho.dataset.ordenar);

    if (e.target.closest('[data-acao="limpar-busca"]')) {
      $("busca-vagas").value = "";
      busca = "";
      return repintar();
    }

    const linha = e.target.closest("tr[data-id]");
    if (linha) abrirGaveta(linha.dataset.id).catch((erro) => aviso.erro(erro.message));
  });
  $("tabela-vagas").addEventListener("keydown", (e) => {
    const cabecalho = e.target.closest("th[data-ordenar]");
    if (cabecalho && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      return trocarOrdem(cabecalho.dataset.ordenar);
    }
    const linha = e.target.closest("tr[data-id]");
    if (linha && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      abrirGaveta(linha.dataset.id).catch((erro) => aviso.erro(erro.message));
    }
  });

  // A busca não vai ao servidor: repintar é síncrono e cabe entre duas teclas.
  $("busca-vagas").addEventListener("input", (e) => {
    busca = e.target.value;
    repintar();
  });
  $("busca-vagas").addEventListener("keydown", (e) => {
    // Esc limpa a busca em vez de fechar a gaveta — aqui o campo é o contexto.
    if (e.key === "Escape" && busca) {
      e.stopPropagation();
      e.target.value = "";
      busca = "";
      repintar();
    }
  });

  // "/" foca a busca de qualquer lugar, menos de dentro de outro campo.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.ctrlKey || e.metaKey) return;
    if (e.target.matches("input, textarea, select, [contenteditable]")) return;
    if (!$("gaveta").hidden) return;
    e.preventDefault();
    $("busca-vagas").focus();
    $("busca-vagas").select();
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
      await aoMudar().catch(() => {});
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
