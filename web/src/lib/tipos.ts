/** Os contratos que a API devolve. Espelham `app/api/schemas/*.py`. */

export type Formato =
  | "multipla_escolha"
  | "certo_errado"
  | "afirmacoes"
  | "negativa"
  | "texto_base"
  | "codigo"
  | "calculo"
  | "flashcard";

export type Alternativa = { letra: string; texto: string };

export type Agenda = {
  proxima_em: string;
  ultima_em: string | null;
  intervalo_dias: number;
  acertos_seguidos: number;
  total_acertos: number;
  total_erros: number;
  estado: "nova" | "aprendendo" | "dominada" | "adiada";
};

export type Questao = {
  id: string;
  formato: Formato;
  modulo: string;
  topico: string;
  topico_id: string;
  comando: string | null;
  enunciado: string;
  texto_base: string | null;
  texto_base_fonte: string | null;
  codigo: string | null;
  linguagem: string | null;
  alternativas: Alternativa[];
  afirmacoes: string[];
  explicacao: string | null;
  origem: string | null;
  fonte: string | null;
  dificuldade: number;
  agenda: Agenda | null;
  /** Só vem na listagem do acervo. Na fila é `null` — de propósito. */
  gabarito: string | null;
};

export type Resumo = {
  hoje: number;
  de_erro: number;
  novas: number;
  adiadas: number;
  dominadas: number;
  total: number;
  respondidas_hoje: number;
};

export type TopicoResumo = {
  id: string;
  nome: string;
  questoes: number;
  hoje: number;
  dominadas: number;
  com_erro: number;
  proxima_em: string | null;
};

export type ModuloResumo = {
  id: string;
  nome: string;
  trilha: string;
  questoes: number;
  hoje: number;
  dominadas: number;
  com_erro: number;
  proxima_em: string | null;
  topicos: TopicoResumo[];
};

export type Resposta = {
  acertou: boolean;
  gabarito: string;
  explicacao: string | null;
  reagendou: boolean;
  proxima_em: string;
  intervalo_dias: number;
  estado: string;
};

export type Tentativa = {
  id: string;
  respondida_em: string;
  acertou: boolean;
  resposta: string | null;
  tentativa_n: number;
  segundos: number | null;
};

export type Usuario = { nome: string; email: string };

// ── fila de aprovação ──

export type Acao = {
  id: string;
  agente: string;
  tipo: string;
  titulo: string;
  status: string;
  contexto: string | null;
  texto_gerado: string | null;
  texto_final: string | null;
  motivo: string | null;
  /** O que o executor vai precisar. `vaga_id` é o que liga a ação ao PDF. */
  payload: {
    vaga_id?: string;
    avisos?: string[];
    rejeitados?: string[];
    [k: string]: unknown;
  };
  alvo_ref: string | null;
  criada_em: string;
  decidida_em: string | null;
};

// ── candidaturas ──

export const STATUS_VAGA = [
  "quero_candidatar",
  "candidatei",
  "respondeu",
  "entrevista",
  "fim",
] as const;

export const EVENTOS = [
  "enviada",
  "visualizada",
  "respondida",
  "entrevista",
  "recusada",
  "sem_retorno",
] as const;

export type VagaLinha = {
  id: string;
  titulo: string;
  empresa: string | null;
  status: string;
  match_score: number | null;
  modelo: string | null;
  localizacao: string | null;
  senioridade: string | null;
  tem_curriculo: boolean;
  curriculo_gerado_em: string | null;
  created_at: string;
};

export type EventoVaga = {
  evento: string;
  detalhe: string | null;
  ocorreu_em: string;
};

export type VagaDetalhe = VagaLinha & {
  link: string | null;
  contato_nome: string | null;
  contato_email: string | null;
  notas: string | null;
  descricao: string;
  analise_json: Record<string, unknown> | null;
  match_json: Record<string, unknown> | null;
  curriculo_json: Record<string, unknown> | null;
  historico: EventoVaga[];
};

export type Geracao = {
  vaga_id: string;
  curriculo: Record<string, unknown>;
  pdf: string | null;
  acao_id: string | null;
  rejeitados: string[];
  avisos: string[];
  vaga: VagaLinha | null;
};

export type Metricas = {
  funil: Record<string, number>;
  por_status: Record<string, number>;
  taxa_resposta: number | null;
  dias_ate_resposta: number | null;
  followup_vencido: number;
  paradas: Record<string, unknown>[];
  gaps_frequentes: { requisito?: string; n?: number }[];
  score_medio: number | null;
};

// ── transcrição ──

export type TrechoVivo = {
  indice: number;
  segundo: number;
  relogio: string;
  texto: string;
  /** Pré-marcado, nunca removido sozinho — anúncio aparece em aula de marketing. */
  anuncio: boolean;
  /** Já entrou num bloco reescrito: cortar agora obrigaria a refazer a reescrita. */
  processado: boolean;
};

export type SugestaoNota = {
  titulo: string;
  resumo: string;
  destaques: string[];
  pasta: string;
  tags: string[];
  conceitos: string[];
  corrigidos: string[];
  nome_arquivo: string;
  palavras: number;
};

export type EstadoTranscricao = {
  /** ocioso | gravando | processando | revisar */
  estado: string;
  etapa: string | null;
  fonte: string;
  segundos: number;
  palavras: number;
  bloco: number;
  blocos: number;
  trechos: TrechoVivo[];
  erro: string | null;
  sugestao: SugestaoNota | null;
};
