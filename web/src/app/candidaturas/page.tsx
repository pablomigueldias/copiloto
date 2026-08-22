"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Aviso } from "@/components/Dialogo";
import { Cabecalho, Erro, Numero, Vazio } from "@/components/ui";
import { api } from "@/lib/api";
import { useAvisos } from "@/lib/avisos";
import { STATUS_VAGA, type Metricas, type VagaLinha } from "@/lib/tipos";

import { GavetaVaga } from "./GavetaVaga";

const ROTULO: Record<string, string> = {
  quero_candidatar: "quero me candidatar",
  candidatei: "candidatei",
  respondeu: "respondeu",
  entrevista: "entrevista",
  fim: "encerrada",
};

function ColarVaga({
  onCriada,
  onErro,
}: {
  onCriada: (id: string, analisar: boolean) => void;
  onErro: (msg: string, e: unknown) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [descricao, setDescricao] = useState("");
  const [titulo, setTitulo] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [link, setLink] = useState("");
  const [fonte, setFonte] = useState("");
  const [enviando, setEnviando] = useState<"salvar" | "analisar" | null>(null);

  const faltam = Math.max(0, 50 - descricao.trim().length);
  const curta = faltam > 0;

  const salvar = async (analisar: boolean) => {
    setEnviando(analisar ? "analisar" : "salvar");
    try {
      const v = await api.colarVaga({
        descricao: descricao.trim(),
        // Nulo é diferente de vazio: nulo deixa o extrator preencher. O título
        // sai da primeira linha da descrição e o e-mail de contato sai por
        // regex do corpo — preencher à mão só quando o anúncio engana.
        titulo: titulo.trim() || null,
        empresa: empresa.trim() || null,
        link: link.trim() || null,
        fonte: fonte.trim() || null,
      });
      setDescricao("");
      setTitulo("");
      setEmpresa("");
      setLink("");
      setFonte("");
      setAberto(false);
      onCriada(v.id, analisar);
    } catch (e) {
      onErro("Não consegui salvar a vaga", e);
    } finally {
      setEnviando(null);
    }
  };

  if (!aberto)
    return (
      <button
        type="button"
        onClick={() => setAberto(true)}
        className="btn btn-primary"
      >
        Colar uma vaga
      </button>
    );

  const rotulo = "card-kicker mb-[5px] block text-neutral-400";

  return (
    <div className="card elev-sm w-[min(560px,100%)]">
      <div className="mb-3 flex items-baseline gap-3">
        <h3 className="m-0 text-[16px]">Colar uma vaga</h3>
        <button
          type="button"
          onClick={() => setAberto(false)}
          className="btn btn-ghost ml-auto px-2 py-1 text-[12.5px]"
        >
          fechar
        </button>
      </div>

      <label className={rotulo} htmlFor="nova-descricao">
        Descrição — cole o anúncio inteiro
      </label>
      <textarea
        id="nova-descricao"
        className="input mb-1 min-h-[170px] resize-y text-[13.5px]"
        value={descricao}
        autoFocus
        onChange={(e) => setDescricao(e.target.value)}
        placeholder="O texto do anúncio, como veio. É daqui que saem os requisitos, a senioridade e o cruzamento com o Perfil Mestre."
      />
      <p className="m-0 mb-3 text-[12px] text-neutral-600">
        {curta
          ? `faltam ${faltam} caracteres — abaixo de 50 não dá para extrair requisitos`
          : `${descricao.trim().length} caracteres`}
      </p>

      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        <div>
          <label className={rotulo} htmlFor="nova-titulo">
            Título
          </label>
          <input
            id="nova-titulo"
            className="input"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            placeholder="sai da descrição se vazio"
          />
        </div>
        <div>
          <label className={rotulo} htmlFor="nova-empresa">
            Empresa
          </label>
          <input
            id="nova-empresa"
            className="input"
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
          />
        </div>
        <div>
          <label className={rotulo} htmlFor="nova-link">
            Link do anúncio
          </label>
          <input
            id="nova-link"
            className="input"
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="https://…"
          />
        </div>
        <div>
          <label className={rotulo} htmlFor="nova-fonte">
            Onde eu vi
          </label>
          <input
            id="nova-fonte"
            className="input"
            value={fonte}
            onChange={(e) => setFonte(e.target.value)}
            placeholder="LinkedIn, indicação, Gupy…"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={enviando !== null || curta}
          onClick={() => salvar(true)}
          className="btn btn-primary"
        >
          {enviando === "analisar" ? "salvando…" : "salvar e analisar"}
        </button>
        <button
          type="button"
          disabled={enviando !== null || curta}
          onClick={() => salvar(false)}
          className="btn btn-secondary"
        >
          {enviando === "salvar" ? "salvando…" : "só salvar"}
        </button>
        <span className="text-[12px] text-neutral-600">
          Analisar chama o extrator e o cruzamento — leva alguns segundos.
        </span>
      </div>
    </div>
  );
}

export default function Candidaturas() {
  const [vagas, setVagas] = useState<VagaLinha[] | null>(null);
  const [metricas, setMetricas] = useState<Metricas | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<string>("");
  const [aberta, setAberta] = useState<string | null>(null);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(
    (): Promise<void> =>
      Promise.all([api.vagas({ limite: 200 }), api.metricasVagas()])
        .then(([v, m]) => {
          setVagas(v.itens);
          setMetricas(m);
        })
        .catch((e: Error) => setErro(String(e.message ?? e))),
    [],
  );

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const filtradas = useMemo(() => {
    if (!vagas) return null;
    const alvo = busca.trim().toLowerCase();
    return vagas.filter(
      (v) =>
        (!filtro || v.status === filtro) &&
        (!alvo ||
          v.titulo.toLowerCase().includes(alvo) ||
          (v.empresa ?? "").toLowerCase().includes(alvo)),
    );
  }, [vagas, busca, filtro]);

  return (
    <div className="max-w-[1180px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Candidaturas</Cabecalho>
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">
        O que foi enviado
      </h1>
      <p className="m-0 mb-7 max-w-[62ch] text-[15px] text-muted">
        O que respondeu, o que sumiu, e o que precisa de follow-up hoje. A
        métrica mais útil está embaixo: os requisitos que mais se repetem nas
        vagas e que eu não tenho — trinta candidaturas viram uma lista de estudo.
      </p>

      {erro && <Erro>{erro}</Erro>}

      <div className="mb-8 flex flex-wrap gap-[38px]">
        <Numero valor={vagas?.length ?? 0} rotulo="Vagas" />
        <Numero
          valor={
            metricas?.taxa_resposta != null
              ? `${Math.round(metricas.taxa_resposta * 100)}%`
              : "—"
          }
          rotulo="Taxa de resposta"
        />
        <Numero
          valor={
            metricas?.dias_ate_resposta != null
              ? metricas.dias_ate_resposta.toFixed(1)
              : "—"
          }
          rotulo="Dias até responder"
        />
        <Numero
          valor={metricas?.followup_vencido ?? 0}
          rotulo="Follow-up vencido"
          cor="text-accent-300"
        />
        <Numero
          valor={
            metricas?.score_medio != null
              ? Math.round(metricas.score_medio)
              : "—"
          }
          rotulo="Aderência média"
        />
      </div>

      <div className="mb-5 flex flex-wrap items-start gap-3">
        <input
          className="input max-w-[260px]"
          type="search"
          placeholder="Buscar vaga ou empresa"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
        <div className="flex flex-wrap gap-1 rounded-[8px] border border-divider p-[3px]">
          <button
            type="button"
            onClick={() => setFiltro("")}
            className={`rounded-[6px] px-[10px] py-[5px] text-[12.5px] ${
              filtro === ""
                ? "bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent-200"
                : "text-neutral-400 hover:text-text"
            }`}
          >
            todas
          </button>
          {STATUS_VAGA.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFiltro(s)}
              className={`rounded-[6px] px-[10px] py-[5px] text-[12.5px] ${
                filtro === s
                  ? "bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent-200"
                  : "text-neutral-400 hover:text-text"
              }`}
            >
              {ROTULO[s]}
              {metricas?.por_status?.[s] ? (
                <span className="tnum ml-[6px] text-neutral-600">
                  {metricas.por_status[s]}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        <div className="ml-auto w-full max-w-[560px] sm:w-auto">
          <ColarVaga
            onErro={falhou}
            onCriada={async (id, analisar) => {
              setAberta(id);
              if (!analisar) {
                ok("Vaga salva — analise quando quiser");
                void carregar();
                return;
              }
              ok("Vaga salva — extraindo os requisitos…");
              try {
                await api.analisarVaga(id);
                ok("Requisitos extraídos e aderência calculada");
              } catch (e) {
                falhou("Salvei, mas a análise falhou", e);
              }
              void carregar();
            }}
          />
        </div>
      </div>

      <div className="grid items-start gap-[clamp(28px,4vw,56px)] lg:grid-cols-[minmax(0,7fr)_minmax(240px,3fr)]">
        <section>
          {!vagas && <p className="text-[13px] text-neutral-500">carregando…</p>}
          {vagas?.length === 0 && (
            <Vazio titulo="Nenhuma vaga ainda">
              Cole uma descrição de vaga para o agente extrair os requisitos,
              cruzar com o Perfil Mestre e escrever um currículo adaptado.
            </Vazio>
          )}

          {filtradas && filtradas.length > 0 && (
            <div className="overflow-x-auto">
              <table className="table min-w-[640px]">
                <thead>
                  <tr>
                    <th>Vaga</th>
                    <th className="w-[130px]">Status</th>
                    <th className="w-[70px]">Match</th>
                    <th className="w-[60px]">CV</th>
                    <th className="w-[80px]">Entrou</th>
                  </tr>
                </thead>
                <tbody>
                  {filtradas.map((v) => (
                    <tr
                      key={v.id}
                      onClick={() => setAberta(v.id)}
                      className="cursor-pointer hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                    >
                      <td>
                        <div className="text-[14px]">{v.titulo}</div>
                        <div className="text-[12px] text-neutral-500">
                          {[v.empresa, v.senioridade, v.localizacao]
                            .filter(Boolean)
                            .join(" · ") || "—"}
                        </div>
                      </td>
                      <td>
                        <span className="tag tag-neutral">
                          {ROTULO[v.status] ?? v.status}
                        </span>
                      </td>
                      <td className="tnum text-[13px] text-accent-300">
                        {v.match_score ?? "—"}
                      </td>
                      <td className="text-[13px] text-neutral-400">
                        {v.tem_curriculo ? "✓" : "—"}
                      </td>
                      <td className="tnum text-[12.5px] text-neutral-500">
                        {new Intl.DateTimeFormat("pt-BR", {
                          day: "2-digit",
                          month: "2-digit",
                        }).format(new Date(v.created_at))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section>
          <h2 className="m-0 mb-4 text-[19px]">O que o mercado pediu</h2>
          {metricas?.gaps_frequentes?.length ? (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {metricas.gaps_frequentes.slice(0, 12).map((g, i) => (
                <li
                  key={i}
                  className="flex items-baseline justify-between gap-3 text-[13.5px]"
                >
                  <span className="text-muted">
                    {g.requisito ?? JSON.stringify(g)}
                  </span>
                  <span className="tnum flex-none text-neutral-600">{g.n}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-[13.5px] text-neutral-500">
              A métrica existe; a amostra ainda não. Ela precisa de vagas
              analisadas para dizer alguma coisa.
            </p>
          )}
        </section>
      </div>

      {aberta && (
        <GavetaVaga
          key={aberta}
          vagaId={aberta}
          onFechar={() => setAberta(null)}
          onMudou={() => void carregar()}
          onOk={ok}
          onErro={falhou}
        />
      )}

      {aviso && <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />}
    </div>
  );
}
