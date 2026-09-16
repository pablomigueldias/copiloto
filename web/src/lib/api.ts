/**
 * O cliente da API.
 *
 * Tudo passa por `/api/*` no mesmo host — o `next.config.ts` reescreve para o
 * FastAPI em dev. Isso não é conveniência: o backend autentica por **cookie de
 * sessão**, e cookie de sessão em origem cruzada exige SameSite=None, HTTPS e
 * uma discussão de CORS que não precisa existir num app que roda na minha
 * máquina. Mesma origem, cookie viaja, e acabou.
 *
 * O CSRF segue a convenção do backend: o token está num cookie legível e volta
 * no header em toda mutação.
 */
import type {
  Acao,
  Banca,
  EstadoTranscricao,
  Geracao,
  Metricas,
  ModuloResumo,
  Questao,
  Resposta,
  Resumo,
  Tentativa,
  Usuario,
  VagaDetalhe,
  VagaLinha,
} from "./tipos";

/** Disparado no `window` depois de cada escrita bem-sucedida. */
export const MUTOU = "copiloto:mutou";

export class ApiErro extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiErro";
  }
}

function cookie(nome: string): string | null {
  if (typeof document === "undefined") return null;
  const achado = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${nome}=`));
  return achado ? decodeURIComponent(achado.slice(nome.length + 1)) : null;
}

async function req<T>(caminho: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");

  // `__Host-csrf` sob HTTPS, `csrf_token` em http local — os dois nomes que
  // `app/api/services/auth/csrf.py` pode emitir.
  const csrf = cookie("csrf_token") ?? cookie("__Host-csrf");
  if (csrf) headers.set("X-CSRF-Token", csrf);

  const r = await fetch(`/api${caminho}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!r.ok) {
    let detalhe = r.statusText;
    try {
      const corpo = await r.json();
      detalhe = corpo?.detail ?? detalhe;
    } catch {
      /* resposta sem corpo JSON — fica o statusText */
    }
    throw new ApiErro(r.status, detalhe);
  }
  // Toda mutação avisa a tela inteira. A sidebar mostra contadores que
  // dependem de coisas escritas noutras telas — o módulo que eu apaguei aqui,
  // a questão que eu respondi ali — e recarregá-la só na troca de rota deixava
  // "Eí · 0" no menu depois de o módulo já não existir.
  if (init?.method && init.method !== "GET" && typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(MUTOU, { detail: caminho }));
  }

  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

const qs = (p: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) {
    if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  }
  const t = s.toString();
  return t ? `?${t}` : "";
};

export const api = {
  // ── auth ──
  eu: () => req<Usuario>("/auth/me"),
  entrar: (email: string, senha: string) =>
    req<Usuario>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, senha }),
    }),
  sair: () => req<{ mensagem: string }>("/auth/logout", { method: "POST" }),

  // ── estudo ──
  resumo: () => req<Resumo>("/estudo/resumo"),
  modulos: () => req<ModuloResumo[]>("/estudo/modulos"),
  bancas: () => req<Banca[]>("/estudo/bancas"),
  /**
   * `ativa: false` tira a banca da fila do dia — e só isso.
   *
   * Nenhuma questão, agenda ou tentativa é tocada, e por isso o botão não
   * pergunta nada antes: é reversível num clique. É o oposto de apagar o
   * módulo, que leva o histórico junto e exige confirmação com o número na mão.
   */
  editarBanca: (id: string, campos: { nome?: string; ativa?: boolean; ordem?: number }) =>
    req<{ id: string; nome: string; ativa: boolean; ordem: number }>(
      `/estudo/bancas/${id}`,
      { method: "PATCH", body: JSON.stringify(campos) },
    ),
  /**
   * Deixa só uma banca em estudo, pausando as outras num clique.
   *
   * Trocar de concurso é uma frase só ("agora é esta"), e dez cliques para
   * dizê-la fazem a pessoa não dizer. O efeito é o mesmo de pausar cada uma à
   * mão — nada é apagado — e `retomarTodasBancas` desfaz.
   */
  focarBanca: (id: string) =>
    req<{ banca: string; bancas_pausadas: number; questoes_pausadas: number }>(
      `/estudo/bancas/${id}/focar`,
      { method: "POST" },
    ),
  retomarTodasBancas: () =>
    req<{ bancas_retomadas: number }>("/estudo/bancas/ativar-todas", {
      method: "POST",
    }),
  /**
   * A figura da questão. É `GET` direto na tag `<img>`, não `fetch`: o arquivo
   * é servido por `StaticFiles` no FastAPI e chega pelo mesmo rewrite `/api/*`
   * do `next.config.ts` que o resto usa.
   */
  urlImagem: (arquivo: string) => `/api/estudo/imagens/${arquivo}`,
  criarModulo: (corpo: { nome: string; trilha: string; ordem?: number }) =>
    req<{ id: string; nome: string; trilha: string; ordem: number }>(
      "/estudo/modulos",
      { method: "POST", body: JSON.stringify(corpo) },
    ),
  editarModulo: (id: string, campos: { nome?: string; trilha?: string }) =>
    req<{ id: string; nome: string; trilha: string; ordem: number }>(
      `/estudo/modulos/${id}`,
      { method: "PATCH", body: JSON.stringify(campos) },
    ),
  /** `forcar` leva as questões e todo o histórico de respostas junto. */
  apagarModulo: (id: string, forcar = false) =>
    req<{ questoes_apagadas: number }>(
      `/estudo/modulos/${id}${forcar ? "?forcar=true" : ""}`,
      { method: "DELETE" },
    ),
  criarTopico: (moduloId: string, corpo: { nome: string; ordem?: number }) =>
    req<{ id: string; modulo_id: string; nome: string; ordem: number }>(
      `/estudo/modulos/${moduloId}/topicos`,
      { method: "POST", body: JSON.stringify(corpo) },
    ),
  editarTopico: (id: string, campos: { nome?: string }) =>
    req<{ id: string; modulo_id: string; nome: string; ordem: number }>(
      `/estudo/topicos/${id}`,
      { method: "PATCH", body: JSON.stringify(campos) },
    ),
  apagarTopico: (id: string, forcar = false) =>
    req<{ questoes_apagadas: number }>(
      `/estudo/topicos/${id}${forcar ? "?forcar=true" : ""}`,
      { method: "DELETE" },
    ),
  fila: (
    p: {
      topico_id?: string;
      modulo_id?: string;
      banca_id?: string;
      questao_id?: string;
      todas?: string;
      limite?: number;
    } = {},
  ) =>
    req<{ total: number; itens: Questao[] }>(`/estudo/fila${qs(p)}`),
  questoes: (
    p: {
      topico_id?: string;
      modulo_id?: string;
      banca_id?: string;
      busca?: string;
      limite?: number;
      offset?: number;
    } = {},
  ) => req<{ total: number; itens: Questao[] }>(`/estudo/questoes${qs(p)}`),
  questao: (id: string) => req<Questao>(`/estudo/questoes/${id}`),
  responder: (
    id: string,
    corpo: { resposta: string; tentativa_n?: number; segundos?: number },
  ) =>
    req<Resposta>(`/estudo/questoes/${id}/responder`, {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  adiar: (id: string, dias?: number) =>
    req<{ proxima_em: string; intervalo_dias: number; estado: string }>(
      `/estudo/questoes/${id}/adiar`,
      { method: "POST", body: JSON.stringify({ dias: dias ?? null }) },
    ),
  historico: (id: string) =>
    req<Tentativa[]>(`/estudo/questoes/${id}/historico`),
  editarQuestao: (id: string, campos: Record<string, unknown>) =>
    req<Questao>(`/estudo/questoes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(campos),
    }),
  /** Uma questão só. Leva o histórico de tentativas dela junto, e devolve quantas. */
  apagarQuestao: (id: string) =>
    req<{ tentativas_apagadas: number }>(`/estudo/questoes/${id}`, {
      method: "DELETE",
    }),
  criarQuestao: (corpo: Record<string, unknown>) =>
    req<Questao>("/estudo/questoes", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),

  // ── fila de aprovação ──
  filaAprovacao: (status = "pendente") =>
    req<{ total: number; por_status: Record<string, number>; itens: Acao[] }>(
      `/fila${qs({ status, limite: 100 })}`,
    ),
  decidir: (
    acaoId: string,
    corpo: { decisao: "aprovar" | "rejeitar"; texto_final?: string; motivo?: string },
  ) =>
    req<Record<string, unknown>>(`/fila/${acaoId}/decidir`, {
      method: "POST",
      body: JSON.stringify(corpo),
    }),

  // ── candidaturas (o router tem prefixo `/api/vagas`: a vaga é a entidade,
  //    a candidatura é o que eu faço com ela) ──
  vagas: (p: Record<string, string | number | undefined> = {}) =>
    req<{ total: number; itens: VagaLinha[] }>(`/vagas${qs(p)}`),
  vaga: (id: string) => req<VagaDetalhe>(`/vagas/${id}`),
  colarVaga: (corpo: {
    descricao: string;
    titulo?: string | null;
    empresa?: string | null;
    link?: string | null;
    fonte?: string | null;
  }) => req<VagaLinha>("/vagas", { method: "POST", body: JSON.stringify(corpo) }),
  editarVaga: (id: string, campos: Record<string, unknown>) =>
    req<VagaDetalhe>(`/vagas/${id}`, {
      method: "PATCH",
      body: JSON.stringify(campos),
    }),
  apagarVaga: (id: string) => req<void>(`/vagas/${id}`, { method: "DELETE" }),
  analisarVaga: (id: string) =>
    req<VagaDetalhe>(`/vagas/${id}/analisar?forcar=true`, { method: "POST" }),
  gerarCurriculo: (id: string, reanalisar = false) =>
    req<Geracao>(`/vagas/${id}/curriculo${qs({ reanalisar: reanalisar ? "true" : "" })}`, {
      method: "POST",
    }),
  curriculoTexto: (id: string) =>
    req<{ vaga_id: string; texto: string }>(`/vagas/${id}/curriculo.txt`),
  salvarCurriculo: (id: string, texto: string) =>
    req<{ vaga_id: string; texto: string; pdf: string | null }>(
      `/vagas/${id}/curriculo`,
      { method: "PUT", body: JSON.stringify({ texto }) },
    ),
  registrarEvento: (id: string, evento: string, detalhe?: string) =>
    req<VagaLinha>(`/vagas/${id}/evento`, {
      method: "POST",
      body: JSON.stringify({ evento, detalhe: detalhe ?? null }),
    }),
  metricasVagas: () => req<Metricas>("/vagas/metricas"),
  /** O PDF é `GET` e abre no visualizador — o mesmo arquivo que o ATS lê. */
  urlCurriculoPdf: (id: string) => `/api/vagas/${id}/curriculo.pdf`,

  // ── conhecimento ──
  buscarConhecimento: (q: string, limite = 8) =>
    req<Record<string, unknown>>(`/conhecimento/buscar${qs({ q, limite })}`),

  // ── transcrição ──
  estadoTranscricao: () => req<EstadoTranscricao>("/transcricao/estado"),
  destinosTranscricao: () =>
    req<{ pastas: string[]; tags: string[]; vault: string }>(
      "/transcricao/destinos",
    ),
  iniciarTranscricao: (fonte: "sistema" | "mic") =>
    req<EstadoTranscricao>("/transcricao/iniciar", {
      method: "POST",
      body: JSON.stringify({ fonte }),
    }),
  pararTranscricao: () =>
    req<EstadoTranscricao>("/transcricao/parar", { method: "POST" }),
  cortarTrecho: (indice: number) =>
    req<EstadoTranscricao>(`/transcricao/trecho/${indice}`, { method: "DELETE" }),
  salvarNota: (corpo: {
    titulo: string;
    pasta: string;
    tags: string[];
    nome_arquivo?: string | null;
  }) =>
    req<{ caminho: string; chunks: number }>("/transcricao/salvar", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  descartarTranscricao: () =>
    req<void>("/transcricao/descartar", { method: "POST" }),

  painel: (blocos?: string) =>
    req<Record<string, unknown>>(`/painel${qs({ blocos })}`),
};
