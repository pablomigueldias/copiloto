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
  /** Nulos na questão inédita — ela não é de banca nenhuma. */
  banca: string | null;
  banca_id: string | null;
  comando: string | null;
  enunciado: string;
  texto_base: string | null;
  texto_base_fonte: string | null;
  codigo: string | null;
  linguagem: string | null;
  alternativas: Alternativa[];
  afirmacoes: string[];
  /** Arquivo em `data/estudo/imagens`; a URL sai de `api.urlImagem()`. */
  imagem: string | null;
  imagem_alt: string | null;
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
  /** Fora do estudo por estarem em banca pausada. Não somem, só não voltam. */
  pausadas: number;
  respondidas_hoje: number;
};

/**
 * Quem aplica a prova, e se eu estou estudando para ela agora.
 *
 * `id` é nulo na linha das inéditas: questão sem banca não se pausa nem se
 * renomeia, e a tela usa a ausência do id para não oferecer os botões.
 */
export type Banca = {
  id: string | null;
  nome: string;
  ativa: boolean;
  ordem: number;
  questoes: number;
  hoje: number;
  dominadas: number;
  com_erro: number;
};

export type TopicoResumo = {
  id: string;
  nome: string;
  /** Só as em estudo — banca ou tópico pausado vão para `pausadas`. */
  questoes: number;
  hoje: number;
  dominadas: number;
  com_erro: number;
  pausadas: number;
  proxima_em: string | null;
  /** `false` = tópico fora do edital, fora da fila até eu retomar. */
  ativo: boolean;
};

export type ModuloResumo = {
  id: string;
  nome: string;
  trilha: string;
  questoes: number;
  hoje: number;
  dominadas: number;
  com_erro: number;
  pausadas: number;
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

// ── A redação (app/blog/) ───────────────────────────────────────────

export type EstadoPost =
  | "pauta"
  | "rascunho"
  | "pronto"
  | "publicado"
  | "arquivado";

/** O público que cada camada atende. `todos` é o fechamento. */
export type PublicoPost =
  | "entusiasta"
  | "cliente"
  | "tecnico"
  | "recrutador"
  | "todos";

export type Sinal = {
  ok: boolean;
  texto: string;
  /** O que fazer quando está vermelho. A regra mora no sistema, não na memória. */
  dica: string | null;
};

export type Camada = {
  id: string;
  rotulo: string;
  publico: PublicoPost;
  pergunta: string;
  ok: boolean;
  sinais: Sinal[];
};

export type Diagnostico = {
  camadas: Camada[];
  camadas_ok: boolean;
  falta: string[];
  frontmatter_erros: string[];
  exportavel: boolean;
  palavras: number;
  minutos: number;
  /** Os `{{FALTA: …}}` abertos. Bloqueiam o `pronto`. */
  faltas: string[];
  alteracoes_nao_publicadas: boolean;
};

export type Check = {
  nome: string;
  /** SUCCESS | FAILURE | PENDENTE | … — o que o GitHub devolveu. */
  resultado: string;
  url: string | null;
};

export type SituacaoPr = {
  /** false = post ainda sem PR. Diferente de "existe e está pendente". */
  existe: boolean;
  estado: string | null;
  url?: string | null;
  checks: Check[];
  checks_verdes: boolean;
  merge_status?: string | null;
  mergeavel: boolean;
};

export type PostLinha = {
  id: string;
  slug: string | null;
  titulo: string;
  descricao: string | null;
  estado: EstadoPost;
  pilar: string | null;
  tags: string[];
  palavras: number;
  camadas_ok: boolean;
  data_publicacao: string | null;
  exportado_em: string | null;
  pr_numero: number | null;
  pr_url: string | null;
  publicado_em: string | null;
  linkedin_em: string | null;
  linkedin_postado_em: string | null;
  /** Post no ar editado aqui e ainda não republicado. */
  alteracoes_nao_publicadas: boolean;
  /** A data da última correção que foi ao ar. */
  atualizado: string | null;
  /** Há PR aberto esperando o merge (post novo ou atualização). */
  pr_aberto: boolean;
  updated_at: string;
};

export type PostDetalhe = PostLinha & {
  corpo: string;
  /** Nunca vai para o MDX: é o que eu não publico. */
  notas: string | null;
  origem: Record<string, string>[];
  linkedin_texto: string | null;
  diagnostico: Diagnostico;
  created_at: string;
};

// ── Etapa 12: vault, geração, distribuição e o painel da redação ──

export type CandidataVault = {
  /** Relativo ao vault. É o que vai para `origem`. */
  caminho: string;
  titulo: string;
  pilar: string | null;
  tags: string[];
  palavras: number;
  trecho: string;
  /** A pauta que já nasceu desta nota, se houver. */
  post_id: string | null;
};

export type SituacaoGeracao = {
  disponivel: boolean;
  /** Por que não dá para gerar agora (sem chave, teto do mês). */
  motivo: string | null;
  gasto_usd: number;
  teto_usd: number;
  modelo: string;
};

export type RascunhoGerado = {
  rodadas: number;
  /** O que a régua ainda reprova depois das voltas. */
  pendentes: string[];
  faltas: string[];
  palavras: number;
  gasto_usd: number;
};

export type LinkedinGerado = { texto: string; pendentes: string[]; gasto_usd: number };

export type TrechoFonte = { rotulo: string; texto: string };

export type Parecido = { titulo: string; url: string; trecho: string };

export type TipoPasso =
  | "publicar"
  | "pr"
  | "linkedin"
  | "escrever"
  | "gerar"
  | "origem"
  | "pauta"
  | "calendario";

export type Passo = {
  tipo: TipoPasso;
  titulo: string;
  detalhe: string;
  post_id: string | null;
  /** O rótulo do botão. Sem ele, o passo é só aviso. */
  acao: string | null;
};

export type PainelBlog = {
  hoje: string;
  funil: Record<EstadoPost, number>;
  m4: { publicados: number; minimo: number; completo: number };
  cadencia: {
    ultimos_30_dias: number;
    dias_desde_ultimo: number | null;
    ultimo: string | null;
  };
  pilares: { pilar: string; publicados: number; na_fila: number; dias_sem_post: number | null }[];
  calendario: {
    terca: string;
    posts: { id: string; titulo: string; estado: EstadoPost; data: string | null }[];
  }[];
  parados: { id: string; titulo: string; dias: number | null }[];
  divulgacao_ativa: boolean;
  gerar: SituacaoGeracao;
  candidatas_vault: number;
  proximos: Passo[];
};

export type VersaoPost = {
  numero: number;
  titulo: string;
  palavras: number;
  criada_em: string;
};

export type VocabularioBlog = {
  pilares: string[];
  tags: string[];
  tags_max: number;
  /** [mínimo, máximo] de caracteres, como o schema do blog exige. */
  titulo: [number, number];
  descricao: [number, number];
};

// ── quadro de pendências (/pendencias) ──

export type ColunaPendencia = "a_fazer" | "fazendo" | "feito";

export type Pendencia = {
  id: string;
  titulo: string;
  descricao: string | null;
  topico: string;
  /** O gatilho como foi escrito: "agora", "antes do 1º contrato", "03/10". */
  quando: string | null;
  /** Só quando há um dia de verdade (AAAA-MM-DD). */
  prazo: string | null;
  onde: string | null;
  coluna: ColunaPendencia;
  ordem: number;
  concluida_em: string | null;
  created_at: string;
};

export type QuadroPendencias = { topicos: string[]; itens: Pendencia[] };

export type PendenciaCampos = {
  titulo?: string;
  topico?: string;
  descricao?: string | null;
  quando?: string | null;
  prazo?: string | null;
  onde?: string | null;
  coluna?: ColunaPendencia;
  ordem?: number;
};

// ── CRM comercial (/comercial) ──

export type EmpresaLinha = {
  id: number;
  nome: string;
  segmento: string | null;
  bairro: string | null;
  pessoa_fisica: boolean;
  cnes: string | null;
  emails: string[];
  telefones: string[];
  /** Lead aberto no CRM, se já foi trazida. */
  lead_id: number | null;
};

export type PaginaEmpresas = { total: number; itens: EmpresaLinha[] };

export type FiltroEmpresas = {
  termo?: string;
  segmento?: string;
  bairro?: string;
  so_com_email?: boolean;
  incluir_no_crm?: boolean;
  offset?: number;
};

export type TrazerResposta = {
  trazidos: number[];
  /** estabelecimento → por que ficou de fora */
  pulados: Record<string, string>;
};

export type LeadLinha = {
  id: number;
  nome: string;
  estagio: string;
  email: string | null;
  /** A clínica publica o e-mail no próprio site (regras-prospeccao §4). */
  email_confirmado: boolean;
  site: string | null;
  proxima_acao: string | null;
  pesquisado_em: string | null;
  criado_em: string;
};

export type FatoFicha = { valor: string | number | boolean; fonte: string };

export type FichaDados = {
  site: string;
  paginas: string[];
  emails: FatoFicha[];
  whatsapp: FatoFicha | null;
  agendamento_online: FatoFicha | null;
  psicologos_crp: FatoFicha | null;
  o_que_faz: FatoFicha | null;
  gancho: FatoFicha | null;
  com_javascript?: string[];
  parou_porque?: string;
};

export type Interacao = {
  id: number;
  canal: string;
  direcao: string;
  tipo: string | null;
  texto: string | null;
  dados: FichaDados | null;
  criado_em: string;
};

export type TarefaCrm = {
  id: number;
  tipo: string;
  vence_em: string;
  feita_em: string | null;
};

export type LeadDetalhe = LeadLinha & {
  email_fonte: string | null;
  telefone: string | null;
  estabelecimento_id: number | null;
  interacoes: Interacao[];
  tarefas: TarefaCrm[];
  rascunhos: RascunhoCrm[];
};

/** Um texto do Redator: na fila, aprovado esperando o envio, ou já enviado. */
export type RascunhoCrm = {
  acao_id: string;
  tipo: "email_frio" | "lembrete_frio";
  status: "pendente" | "aprovada" | "editada" | "rejeitada";
  assunto: string;
  corpo: string;
  motivo: string | null;
  avisos: string[];
  problemas: string[];
  criada_em: string;
  enviado_em: string | null;
};

export type EscreverResposta = {
  acao_id: string;
  avisos: string[];
  lead: LeadDetalhe;
};

export type PesquisarResposta = {
  status: "ok" | "sem_site" | "site_fora" | "nao_e_da_clinica";
  email_confirmado: boolean;
  mensagem: string;
  lead: LeadDetalhe;
};

// ── o cadastro do CRM (empresa, contato, negócio, atividade) ──

export type TipoRegistro = "empresa" | "contato" | "negocio" | "atividade";

export type OpcoesCrm = Record<
  "estagio" | "status_empresa" | "origem" | "tipo_tarefa" | "canal",
  Record<string, string>
>;

export type CampoRegistro = {
  /** Nulo quando o campo só se lê aqui. */
  campo: string | null;
  rotulo: string;
  tipo: string;
  valor: string | number | boolean | null;
  exibicao: string;
  opcoes: { valor: string; rotulo: string }[];
};

export type LinkRegistro = {
  tipo: TipoRegistro;
  id: number;
  nome: string;
  sub: string | null;
};

export type EventoLinha = {
  quando: string;
  tipo: "interacao" | "transicao";
  canal: string | null;
  direcao: string | null;
  rotulo: string | null;
  texto: string | null;
  lead_id: number;
  negocio_nome: string | null;
};

export type Registro = {
  tipo: TipoRegistro;
  id: number;
  titulo: string;
  campos: CampoRegistro[];
  grupos: { titulo: string; tipo: TipoRegistro; itens: LinkRegistro[] }[];
  notas: string | null;
  linha_do_tempo: EventoLinha[];
  valores: Record<string, string | number | boolean | null>;
};

export type EmpresaCrm = {
  id: number;
  nome: string;
  status: string;
  segmento: string | null;
  site: string | null;
  email: string | null;
  telefone: string | null;
  bairro: string | null;
  cidade: string | null;
  uf: string | null;
  estabelecimento_id: number | null;
  n_contatos: number;
  n_negocios: number;
};

export type ContatoCrm = {
  id: number;
  nome: string;
  cargo: string | null;
  decisor: boolean;
  email: string | null;
  telefone: string | null;
  linkedin: string | null;
  empresa_id: number | null;
  empresa_nome: string | null;
};

export type NegocioCrm = {
  id: number;
  nome: string;
  estagio: string;
  origem: string;
  valor_estimado: number | null;
  empresa_id: number | null;
  empresa_nome: string | null;
  contato_id: number | null;
  contato_nome: string | null;
  email: string | null;
  email_confirmado: boolean;
  proxima_acao: string | null;
  proxima_em: string | null;
  motivo_perda: string | null;
  tarefas_abertas: number;
  pode_ir: string[];
  criado_em: string;
  atualizado_em: string;
};

export type AtividadeCrm = {
  id: number;
  tipo: string;
  descricao: string | null;
  vence_em: string;
  feita_em: string | null;
  atrasada: boolean;
  lead_id: number;
  negocio_nome: string;
  negocio_estagio: string;
  empresa_id: number | null;
  empresa_nome: string | null;
};

export type PainelCrm = {
  negocios_abertos: number;
  valor_aberto: number;
  ganhos: number;
  valor_ganho: number;
  perdidos: number;
  por_estagio: {
    estagio: string;
    rotulo: string;
    total: number;
    valor: number;
  }[];
  tarefas_abertas: number;
  tarefas_atrasadas: number;
  tarefas_hoje: number;
  empresas: number;
  clientes: number;
  contatos: number;
  motivos_perda: { motivo: string; total: number }[];
  proximas: AtividadeCrm[];
};

export type CamposCrm = Record<string, string | number | boolean | null>;

// ── simulado ──

export type Materia = "pt" | "mat" | "en" | "bd";

export type SimuladoResumo = {
  id: string;
  numero: number;
  estado: "em_andamento" | "finalizado";
  iniciado_em: string;
  finalizado_em: string | null;
  total: number;
  respondidas: number;
  acertos: number | null;
  nota: number | null;
  habilitado: boolean | null;
};

export type ReforcoResumo = {
  id: string;
  simulado_id: string;
  materia: Materia;
  materia_nome: string;
  grupo: string | null;
  assunto: string;
  rodada: number;
  estado: "aguardando_questoes" | "pronto" | "aprovado" | "reprovado";
  erros_no_simulado: number;
  total: number;
  respondidas: number;
  acertos: number | null;
  minimo: number;
  /** A escrita das questões pelo botão: null = ninguém pediu. */
  geracao: "gerando" | "erro" | "ok" | null;
  geracao_em: string | null;
  geracao_erro: string | null;
};

export type EstadoSimulado = {
  liberado: boolean;
  em_andamento: SimuladoResumo | null;
  reforcos_pendentes: ReforcoResumo[];
  reforcos_concluidos: ReforcoResumo[];
  historico: SimuladoResumo[];
  materias: { chave: Materia; nome: string; questoes: number; estoque: number }[];
  nota_minima: number;
};

/** A questão como o simulado a manda: sem gabarito até entregar. */
export type QuestaoProva = {
  id: string;
  formato: string;
  comando: string | null;
  enunciado: string;
  texto_base: string | null;
  texto_base_fonte: string | null;
  codigo: string | null;
  linguagem: string | null;
  alternativas: { letra: string; texto: string }[];
  afirmacoes: string[];
  imagem: string | null;
  imagem_alt: string | null;
  banca: string | null;
  origem: string | null;
  gabarito: string | null;
  explicacao: string | null;
};

export type ItemSimulado = {
  ordem: number;
  materia: Materia;
  materia_nome: string;
  assunto: string | null;
  revisao: boolean | null;
  resposta: string | null;
  acertou: boolean | null;
  questao: QuestaoProva;
};

export type SimuladoDetalhe = SimuladoResumo & { itens: ItemSimulado[] };

export type AssuntoErrado = {
  assunto: string;
  grupo: string | null;
  total: number;
  erros: number;
};

export type ResultadoSimulado = SimuladoResumo & {
  nota_minima: number;
  por_materia: {
    chave: Materia;
    nome: string;
    acertos: number;
    total: number;
    percentual: number;
    assuntos_errados: AssuntoErrado[];
  }[];
  erros: ItemSimulado[];
  reforcos: ReforcoResumo[];
};

export type ReforcoDetalhe = ReforcoResumo & {
  itens: {
    ordem: number;
    resposta: string | null;
    acertou: boolean | null;
    questao: QuestaoProva;
  }[];
};

export type RespostaReforco = {
  ordem: number;
  acertou: boolean;
  gabarito: string;
  explicacao: string | null;
  reforco: ReforcoResumo;
};
