"use client";

import { useCallback, useEffect, useState } from "react";

import { Dialogo } from "@/components/Dialogo";
import { api } from "@/lib/api";
import { EVENTOS, STATUS_VAGA, type VagaDetalhe } from "@/lib/tipos";

const ROTULO_STATUS: Record<string, string> = {
  quero_candidatar: "quero me candidatar",
  candidatei: "candidatei",
  respondeu: "respondeu",
  entrevista: "entrevista",
  fim: "encerrada",
};

const CAMPOS: [keyof VagaDetalhe, string][] = [
  ["titulo", "Título"],
  ["empresa", "Empresa"],
  ["link", "Link"],
  ["localizacao", "Localização"],
  ["modelo", "Modelo"],
  ["senioridade", "Senioridade"],
  ["contato_nome", "Contato"],
  ["contato_email", "E-mail do contato"],
];

function haQuanto(iso: string): string {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "agora";
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  return `há ${Math.floor(s / 86400)} d`;
}

function Tags({ itens, prefixo }: { itens?: unknown; prefixo?: string }) {
  const lista = Array.isArray(itens) ? (itens as string[]) : [];
  if (!lista.length)
    return <p className="m-0 text-[13px] text-neutral-600">—</p>;
  return (
    <div className="flex flex-wrap gap-[6px]">
      {lista.map((x, i) => (
        <span key={i} className="tag tag-neutral">
          {prefixo}
          {String(x)}
        </span>
      ))}
    </div>
  );
}

function Secao({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-divider pt-4">
      <h3 className="m-0 mb-3 text-[15px]">{titulo}</h3>
      {children}
    </section>
  );
}

export function GavetaVaga({
  vagaId,
  onFechar,
  onMudou,
  onErro,
  onOk,
}: {
  vagaId: string;
  onFechar: () => void;
  onMudou: () => void;
  onErro: (msg: string, e: unknown) => void;
  onOk: (msg: string) => void;
}) {
  const [vaga, setVaga] = useState<VagaDetalhe | null>(null);
  const [rascunho, setRascunho] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [curriculo, setCurriculo] = useState<string | null>(null);
  const [apagando, setApagando] = useState(false);

  const carregar = useCallback(
    (): Promise<void> =>
      api
        .vaga(vagaId)
        .then((v) => {
          setVaga(v);
          setRascunho({});
        })
        .catch((e: Error) => onErro("Não consegui abrir a vaga", e)),
    [vagaId, onErro],
  );

  useEffect(() => {
    void carregar();
  }, [carregar]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && curriculo === null && !apagando) onFechar();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onFechar, curriculo, apagando]);

  const roda = async (
    chave: string,
    fn: () => Promise<unknown>,
    sucesso: string,
    falha: string,
  ) => {
    setOcupado(chave);
    try {
      await fn();
      onOk(sucesso);
      await carregar();
      onMudou();
    } catch (e) {
      onErro(falha, e);
    } finally {
      setOcupado(null);
    }
  };

  const salvarCampos = () => {
    const campos = Object.fromEntries(
      Object.entries(rascunho).filter(([, v]) => v !== undefined),
    );
    if (!Object.keys(campos).length) return;
    void roda(
      "campos",
      () => api.editarVaga(vagaId, campos),
      "Vaga corrigida",
      "Não consegui salvar",
    );
  };

  if (!vaga) {
    return (
      <div className="fixed inset-0 z-50 flex justify-end bg-[rgb(0_0_0/55%)]">
        <aside className="h-full w-[min(620px,100%)] border-l border-divider bg-bg p-6 text-[13px] text-neutral-500">
          carregando…
        </aside>
      </div>
    );
  }

  const analise = (vaga.analise_json ?? {}) as Record<string, unknown>;
  const match = (vaga.match_json ?? {}) as Record<string, unknown>;
  const cur = (vaga.curriculo_json ?? {}) as Record<string, unknown>;
  const sujo = Object.keys(rascunho).length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[rgb(0_0_0/55%)]"
      onClick={() => !sujo && onFechar()}
      role="presentation"
    >
      <aside
        className="elev-lg flex h-full w-[min(620px,100%)] flex-col overflow-y-auto border-l border-divider bg-bg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-divider bg-bg px-6 py-4">
          <div className="min-w-0">
            <div className="truncate text-[15px]">{vaga.titulo}</div>
            <div className="truncate text-[12px] text-neutral-500">
              {vaga.empresa ?? "sem empresa"}
              {vaga.match_score !== null
                ? ` · aderência ${vaga.match_score}/100`
                : ""}
            </div>
          </div>
          <button
            type="button"
            onClick={onFechar}
            className="btn btn-ghost ml-auto px-2 py-1 text-[13px]"
          >
            fechar
          </button>
        </header>

        <div className="flex flex-col gap-5 px-6 py-5">
          {/* ── ações ── */}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={ocupado !== null}
              onClick={() =>
                roda(
                  "gerar",
                  () => api.gerarCurriculo(vagaId, true),
                  "Currículo gerado — confira o PDF",
                  "Não consegui gerar",
                )
              }
              className="btn btn-primary"
            >
              {ocupado === "gerar" ? "gerando…" : "analisar + gerar currículo"}
            </button>
            <button
              type="button"
              disabled={ocupado !== null}
              onClick={() =>
                roda(
                  "analisar",
                  () => api.analisarVaga(vagaId),
                  "Requisitos extraídos e aderência recalculada",
                  "Não consegui analisar",
                )
              }
              className="btn btn-secondary"
            >
              {ocupado === "analisar" ? "analisando…" : "só analisar"}
            </button>
            {vaga.curriculo_gerado_em && (
              <a
                href={api.urlCurriculoPdf(vagaId)}
                target="_blank"
                rel="noopener"
                className="btn btn-secondary"
              >
                ver PDF
              </a>
            )}
          </div>

          {/* ── status ── */}
          <div className="flex flex-wrap items-center gap-3">
            <label className="card-kicker text-neutral-400" htmlFor="status">
              Status
            </label>
            <select
              id="status"
              className="input max-w-[210px]"
              value={vaga.status}
              onChange={(e) =>
                roda(
                  "status",
                  () => api.editarVaga(vagaId, { status: e.target.value }),
                  "Status atualizado",
                  "Não consegui mudar o status",
                )
              }
            >
              {STATUS_VAGA.map((s) => (
                <option key={s} value={s}>
                  {ROTULO_STATUS[s]}
                </option>
              ))}
            </select>
          </div>

          {/* ── campos ── */}
          <Secao titulo="Dados da vaga">
            <div className="grid gap-3 sm:grid-cols-2">
              {CAMPOS.map(([nome, rotulo]) => (
                <div key={nome} className="flex flex-col gap-[5px]">
                  <label
                    className="card-kicker text-neutral-400"
                    htmlFor={`campo-${nome}`}
                  >
                    {rotulo}
                  </label>
                  <input
                    id={`campo-${nome}`}
                    className="input"
                    value={
                      rascunho[nome] ?? ((vaga[nome] as string | null) ?? "")
                    }
                    onChange={(e) =>
                      setRascunho((r) => ({ ...r, [nome]: e.target.value }))
                    }
                  />
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-col gap-[5px]">
              <label className="card-kicker text-neutral-400" htmlFor="notas">
                Minhas notas
              </label>
              <textarea
                id="notas"
                className="input min-h-[70px] resize-y"
                value={rascunho.notas ?? (vaga.notas ?? "")}
                onChange={(e) =>
                  setRascunho((r) => ({ ...r, notas: e.target.value }))
                }
              />
            </div>
            {sujo && (
              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  disabled={ocupado !== null}
                  onClick={salvarCampos}
                  className="btn btn-primary"
                >
                  {ocupado === "campos" ? "salvando…" : "salvar correções"}
                </button>
                <button
                  type="button"
                  onClick={() => setRascunho({})}
                  className="btn btn-ghost"
                >
                  descartar
                </button>
              </div>
            )}
          </Secao>

          {/* ── análise ── */}
          <Secao titulo="Análise da vaga">
            {vaga.analise_json ? (
              <div className="flex flex-col gap-3">
                <div className="tnum text-[13px] text-muted">
                  aderência{" "}
                  <span className="text-accent">
                    {vaga.match_score ?? "—"}
                  </span>
                  /100
                </div>
                <div>
                  <div className="card-kicker mb-[6px]">
                    requisitos obrigatórios
                  </div>
                  <Tags itens={analise.obrigatorios} />
                </div>
                <div>
                  <div className="card-kicker mb-[6px]">o que eu já tenho</div>
                  <Tags itens={match.destaques} prefixo="✓ " />
                </div>
                <div>
                  <div className="card-kicker mb-[6px]">
                    o que falta — vira lista de estudo
                  </div>
                  <Tags itens={match.gaps} prefixo="· " />
                </div>
              </div>
            ) : (
              <p className="m-0 text-[13.5px] text-neutral-500">
                Ainda não analisada — use o botão acima.
              </p>
            )}
          </Secao>

          {/* ── currículo ── */}
          {vaga.curriculo_gerado_em && (
            <Secao titulo="Currículo">
              <div className="tnum mb-2 text-[13px] text-muted">
                gerado {haQuanto(vaga.curriculo_gerado_em)}
                {cur.titulo ? ` · ${String(cur.titulo)}` : ""}
              </div>
              {Array.isArray(cur.avisos) &&
                (cur.avisos as string[]).map((a, i) => (
                  <div key={i} className="mb-1 text-[12.5px] text-accent-300">
                    ⚠ {a}
                  </div>
                ))}
              {Array.isArray(cur.rejeitados) &&
              (cur.rejeitados as string[]).length ? (
                <>
                  <div className="card-kicker mb-[6px] mt-2">
                    a anti-alucinação derrubou
                  </div>
                  <Tags itens={cur.rejeitados} />
                </>
              ) : (
                <p className="m-0 mt-1 text-[12.5px] text-neutral-500">
                  nada rejeitado pela anti-alucinação ✓
                </p>
              )}

              {curriculo === null ? (
                <button
                  type="button"
                  disabled={ocupado !== null}
                  onClick={async () => {
                    setOcupado("abrir-cv");
                    try {
                      setCurriculo((await api.curriculoTexto(vagaId)).texto);
                    } catch (e) {
                      onErro("Não consegui abrir o currículo", e);
                    } finally {
                      setOcupado(null);
                    }
                  }}
                  className="btn btn-secondary mt-3"
                >
                  {ocupado === "abrir-cv" ? "abrindo…" : "editar currículo"}
                </button>
              ) : (
                <div className="mt-3">
                  <textarea
                    className="input min-h-[320px] resize-y font-mono text-[12.5px] leading-[1.6]"
                    value={curriculo}
                    onChange={(e) => setCurriculo(e.target.value)}
                    aria-label="currículo em texto"
                  />
                  <p className="m-0 my-2 text-[12px] leading-[1.5] text-neutral-600">
                    O PDF sai deste texto. Seção que você reescrever de um jeito
                    que o parser não reconheça fica como estava — o texto nunca
                    é jogado fora. A anti-alucinação não roda aqui: quem escreveu
                    foi você, que é a autoridade sobre o próprio currículo.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={ocupado !== null}
                      onClick={() =>
                        roda(
                          "salvar-cv",
                          async () => {
                            const r = await api.salvarCurriculo(
                              vagaId,
                              curriculo,
                            );
                            setCurriculo(r.texto);
                          },
                          "Currículo salvo e PDF reimpresso",
                          "Não consegui salvar",
                        )
                      }
                      className="btn btn-primary"
                    >
                      {ocupado === "salvar-cv"
                        ? "salvando…"
                        : "salvar e reimprimir"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setCurriculo(null)}
                      className="btn btn-ghost"
                    >
                      cancelar
                    </button>
                  </div>
                </div>
              )}
            </Secao>
          )}

          {/* ── eventos ── */}
          <Secao titulo="Histórico">
            <div className="mb-3 flex flex-wrap gap-[6px]">
              {EVENTOS.map((ev) => (
                <button
                  key={ev}
                  type="button"
                  disabled={ocupado !== null}
                  onClick={() =>
                    roda(
                      `ev-${ev}`,
                      () => api.registrarEvento(vagaId, ev),
                      `Registrado: ${ev}`,
                      "Não consegui registrar",
                    )
                  }
                  className="btn btn-secondary px-[10px] py-[4px] text-[12.5px]"
                >
                  {ev}
                </button>
              ))}
            </div>
            {vaga.historico.length === 0 ? (
              <p className="m-0 text-[13px] text-neutral-600">
                Sem eventos ainda.
              </p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-[6px] p-0">
                {[...vaga.historico].reverse().map((e, i) => (
                  <li key={i} className="flex items-baseline gap-3 text-[13px]">
                    <span className="h-[6px] w-[6px] flex-none rounded-full bg-accent-700" />
                    <span>{e.evento}</span>
                    {e.detalhe && (
                      <span className="text-neutral-500">{e.detalhe}</span>
                    )}
                    <span className="tnum ml-auto flex-none text-[12px] text-neutral-600">
                      {haQuanto(e.ocorreu_em)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Secao>

          {/* ── descrição ── */}
          <Secao titulo="Descrição colada">
            <textarea
              className="input min-h-[160px] resize-y text-[13px] leading-[1.6]"
              value={rascunho.descricao ?? vaga.descricao}
              onChange={(e) =>
                setRascunho((r) => ({ ...r, descricao: e.target.value }))
              }
              aria-label="descrição da vaga"
            />
            <p className="m-0 mt-2 text-[12px] text-neutral-600">
              Corrigir aqui e reanalisar é o caminho quando o extrator leu a
              vaga errado.
            </p>
          </Secao>

          <div className="border-t border-divider pt-4">
            <button
              type="button"
              onClick={() => setApagando(true)}
              className="btn btn-ghost text-[13px]"
            >
              apagar esta vaga
            </button>
          </div>
        </div>

        {apagando && (
          <Dialogo
            titulo="Apagar a vaga?"
            descricao="O histórico de eventos vai junto, e isso é irreversível."
            confirmar="apagar"
            perigo
            onCancelar={() => setApagando(false)}
            onConfirmar={async () => {
              setApagando(false);
              try {
                await api.apagarVaga(vagaId);
                onOk("Vaga apagada");
                onMudou();
                onFechar();
              } catch (e) {
                onErro("Não consegui apagar", e);
              }
            }}
          />
        )}
      </aside>
    </div>
  );
}
