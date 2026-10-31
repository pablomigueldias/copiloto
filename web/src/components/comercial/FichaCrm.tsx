"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { ProspeccaoNegocio } from "@/components/comercial/Prospeccao";
import { FormCrm } from "@/components/comercial/FormCrm";
import { Celula, PainelLateral, useOpcoes } from "@/components/comercial/crm";
import { api } from "@/lib/api";
import { useAvisos } from "@/lib/avisos";
import type {
  CamposCrm,
  EventoLinha,
  Registro,
  TipoRegistro,
} from "@/lib/tipos";

type Ref = { tipo: TipoRegistro; id: number };

const ROTULO: Record<TipoRegistro, string> = {
  empresa: "Empresa",
  contato: "Contato",
  negocio: "Negócio",
  atividade: "Atividade",
};

/** O "+ novo" de cada grupo: o formulário abre já ligado ao registro aberto. */
function criarNoGrupo(
  r: Registro,
  grupo: string,
): { tipo: TipoRegistro; inicial: CamposCrm } | null {
  const empresaDoNegocio = r.valores.empresa_id ?? null;
  switch (`${r.tipo}/${grupo}`) {
    case "empresa/Contatos":
      return { tipo: "contato", inicial: { empresa_id: r.id } };
    case "empresa/Negócios": {
      // O negócio já nasce com quem decide, ou com o único contato da empresa.
      const contatos =
        r.grupos.find((g) => g.titulo === "Contatos")?.itens ?? [];
      const quem =
        contatos.find((c) => c.sub?.includes("decisor")) ??
        (contatos.length === 1 ? contatos[0] : null);
      return {
        tipo: "negocio",
        inicial: { empresa_id: r.id, contato_id: quem?.id ?? null },
      };
    }
    case "contato/Negócios":
      return {
        tipo: "negocio",
        inicial: { contato_id: r.id, empresa_id: r.valores.empresa_id ?? null },
      };
    case "negocio/Contato":
      return r.grupos.find((g) => g.titulo === "Contato")?.itens.length
        ? null
        : { tipo: "contato", inicial: { empresa_id: empresaDoNegocio } };
    case "negocio/Atividades":
      return { tipo: "atividade", inicial: { lead_id: r.id } };
    default:
      return null;
  }
}

function dataHora(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function Bloco({
  titulo,
  acao,
  children,
}: {
  titulo: string;
  acao?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="m-0 text-[13px] uppercase tracking-[0.08em] text-neutral-400">
          {titulo}
        </h3>
        {acao}
      </div>
      {children}
    </section>
  );
}

/**
 * A ficha de um registro do CRM e tudo o que está ligado a ele. Clicar num
 * relacionado empilha a ficha dele; "← voltar" desempilha. É o jeito do CRM do
 * prospector de andar entre empresa, contato e negócio sem perder o fio.
 */
export function FichaCrm({
  tipo,
  id,
  onFechar,
  onMudou,
}: {
  tipo: TipoRegistro;
  id: number;
  onFechar: () => void;
  onMudou?: () => void;
}) {
  const [pilha, setPilha] = useState<Ref[]>([{ tipo, id }]);
  const atual = pilha[pilha.length - 1];
  const [dado, setR] = useState<Registro | null>(null);
  // O registro carregado só vale para o topo da pilha: ao empilhar outro, a
  // ficha mostra "carregando" até o dele chegar.
  const r =
    dado && dado.tipo === atual.tipo && dado.id === atual.id ? dado : null;
  const [erro, setErro] = useState<string | null>(null);
  const [form, setForm] = useState<{
    tipo: TipoRegistro;
    id?: number;
    inicial?: CamposCrm;
  } | null>(null);
  const [excluindo, setExcluindo] = useState(false);
  const [perda, setPerda] = useState(false);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .crmRegistro(atual.tipo, atual.id)
      .then((x) => {
        setR(x);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, [atual.tipo, atual.id]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const mudou = (novo?: Registro) => {
    if (novo) setR(novo);
    else carregar();
    onMudou?.();
  };

  const editar = (campo: string) => async (v: string | boolean | null) => {
    try {
      mudou(await api.crmEditar(atual.tipo, atual.id, { [campo]: v }));
      setErro(null);
    } catch (e) {
      setErro((e as Error).message);
      throw e;
    }
  };

  const mover = async (para: string) => {
    if (para === "perdido") {
      setPerda(true);
      return;
    }
    try {
      mudou(await api.crmMover(atual.id, para));
    } catch (e) {
      // Transição proibida volta com o motivo: aparece em cima, não só no tooltip.
      setErro((e as Error).message);
      throw e;
    }
  };

  async function excluir() {
    try {
      await api.crmExcluir(atual.tipo, atual.id);
      setExcluindo(false);
      onMudou?.();
      if (pilha.length > 1) setPilha((p) => p.slice(0, -1));
      else onFechar();
    } catch (e) {
      setExcluindo(false);
      setErro((e as Error).message);
    }
  }

  return (
    <PainelLateral
      titulo={r?.titulo ?? ROTULO[atual.tipo]}
      onFechar={onFechar}
      acoes={
        r && (
          <>
            {r.tipo === "negocio" && (
              <Link
                href={`/comercial/leads/${r.id}`}
                className="btn btn-secondary !text-[13px]"
              >
                página completa
              </Link>
            )}
            <button
              type="button"
              className="btn btn-primary !text-[13px]"
              onClick={() => setForm({ tipo: r.tipo, id: r.id })}
            >
              editar
            </button>
          </>
        )
      }
    >
      <div className="-mt-1 mb-4 flex items-center gap-3 text-[12px] text-neutral-500">
        {pilha.length > 1 && (
          <button
            type="button"
            className="hover:text-text"
            onClick={() => setPilha((p) => p.slice(0, -1))}
          >
            ← voltar
          </button>
        )}
        <span className="rounded-[4px] bg-surface px-[6px] py-[1px] uppercase tracking-[0.08em]">
          {ROTULO[atual.tipo]}
        </span>
        {r && (
          <button
            type="button"
            className="ml-auto hover:text-[#e07f86]"
            onClick={() => setExcluindo(true)}
          >
            excluir
          </button>
        )}
      </div>

      {erro && (
        <p className="mb-4 rounded-[8px] border border-[color-mix(in_srgb,#e07f86_40%,transparent)] px-3 py-2 text-[13px] text-[#e07f86]">
          {erro}
        </p>
      )}

      {!r ? (
        <div className="h-40 animate-pulse rounded-[10px] bg-surface" />
      ) : (
        <div className="flex flex-col gap-6">
          <div className="flex flex-col text-[13.5px]">
            {r.campos.map((c) => (
              <div
                key={c.rotulo}
                className="grid grid-cols-[150px_1fr] items-center gap-2 border-b border-divider py-[7px] last:border-0"
              >
                <span className="text-neutral-500">{c.rotulo}</span>
                <div className="min-w-0 justify-self-start">
                  {c.tipo === "estagio" ? (
                    <Celula
                      valor={c.valor as string}
                      exibicao={c.exibicao}
                      tipo="opcao"
                      opcoes={[
                        { valor: String(c.valor), rotulo: c.exibicao },
                        ...c.opcoes,
                      ]}
                      onSalvar={(v) => mover(String(v))}
                    />
                  ) : c.campo ? (
                    <Celula
                      valor={c.valor}
                      exibicao={c.exibicao}
                      tipo={c.tipo}
                      opcoes={c.opcoes}
                      onSalvar={editar(c.campo)}
                    />
                  ) : (
                    <span className="break-words text-text">{c.exibicao}</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {r.tipo === "negocio" && (
            <Bloco titulo="Prospecção · Pesquisador e e-mail">
              <ProspeccaoNegocio
                key={r.id}
                id={r.id}
                onMudou={() => mudou()}
                ok={ok}
                falhou={falhou}
              />
            </Bloco>
          )}

          {r.grupos.map((g) => {
            const novo = criarNoGrupo(r, g.titulo);
            if (!g.itens.length && !novo) return null;
            return (
              <Bloco
                key={g.titulo}
                titulo={`${g.titulo} (${g.itens.length})`}
                acao={
                  novo && (
                    <button
                      type="button"
                      className="btn btn-ghost !text-[12.5px]"
                      onClick={() =>
                        setForm({ tipo: novo.tipo, inicial: novo.inicial })
                      }
                    >
                      + {ROTULO[novo.tipo].toLowerCase()}
                    </button>
                  )
                }
              >
                {g.itens.length === 0 ? (
                  <p className="m-0 text-[13px] text-neutral-500">
                    nenhum ainda
                  </p>
                ) : (
                  <ul className="m-0 flex list-none flex-col gap-[6px] p-0">
                    {g.itens.map((it) => (
                      <li key={`${it.tipo}-${it.id}`}>
                        <button
                          type="button"
                          onClick={() =>
                            setPilha((p) => [
                              ...p,
                              { tipo: it.tipo, id: it.id },
                            ])
                          }
                          className="flex w-full items-center justify-between gap-2 rounded-[8px] border border-divider bg-surface px-3 py-2 text-left transition-colors hover:border-[color-mix(in_srgb,var(--color-accent)_50%,transparent)]"
                        >
                          <span className="text-[13.5px] text-text">
                            {it.nome}
                          </span>
                          <span className="flex-none text-[12px] text-neutral-500">
                            {it.sub ?? ""} ›
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Bloco>
            );
          })}

          {"notas" in r.valores && (
            <Bloco titulo="Notas">
              <Celula
                valor={r.notas}
                tipo="longo"
                vazio="clique para escrever"
                className="w-full text-[13.5px] leading-[1.55]"
                onSalvar={editar("notas")}
              />
            </Bloco>
          )}

          {r.tipo !== "atividade" && (
            <LinhaDoTempo r={r} onRegistrou={(x) => mudou(x)} />
          )}
        </div>
      )}

      {form && (
        <FormCrm
          tipo={form.tipo}
          id={form.id}
          inicial={form.inicial}
          onFechar={() => setForm(null)}
          onSalvo={() => mudou()}
        />
      )}
      {excluindo && r && (
        <Dialogo
          titulo={`Excluir ${ROTULO[r.tipo].toLowerCase()}`}
          descricao={`Excluir "${r.titulo}"? Não dá para desfazer.${
            r.tipo === "empresa" ? " Os contatos dela vão junto." : ""
          }`}
          confirmar="excluir"
          perigo
          onConfirmar={excluir}
          onCancelar={() => setExcluindo(false)}
        />
      )}
      {perda && (
        <Dialogo
          titulo="Por que perdeu?"
          descricao="O motivo da perda é o dado que ensina o preço e a oferta."
          confirmar="marcar perdido"
          multilinha
          placeholder="ex.: já usa outro sistema; achou caro; não respondeu ao lembrete"
          onConfirmar={async (motivo) => {
            setPerda(false);
            try {
              mudou(await api.crmMover(atual.id, "perdido", motivo));
            } catch (e) {
              setErro((e as Error).message);
            }
          }}
          onCancelar={() => setPerda(false)}
        />
      )}
      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </PainelLateral>
  );
}

function Evento({
  e,
  mostrarNegocio,
}: {
  e: EventoLinha;
  mostrarNegocio: boolean;
}) {
  const opcoes = useOpcoes();
  const cor =
    e.tipo === "transicao"
      ? "var(--color-accent)"
      : e.direcao === "entrada"
        ? "#5fc0b5"
        : e.direcao === "saida"
          ? "#7fa7e0"
          : "#75798c";
  const titulo =
    e.tipo === "transicao"
      ? e.rotulo
      : `${opcoes?.canal[e.canal ?? ""] ?? e.canal}${e.direcao === "entrada" ? " recebido" : e.direcao === "saida" ? " enviado" : ""}${
          e.rotulo && !["manual", "nota"].includes(e.rotulo)
            ? ` · ${e.rotulo}`
            : ""
        }`;
  return (
    <li className="flex gap-[10px] text-[13px]">
      <span
        className="mt-[7px] h-[7px] w-[7px] flex-none rounded-full"
        style={{ background: cor }}
      />
      <div className="min-w-0">
        <div className="text-text">
          {titulo}
          {mostrarNegocio && e.negocio_nome && (
            <span className="text-neutral-500"> · {e.negocio_nome}</span>
          )}
        </div>
        {e.texto && (
          <div className="line-clamp-3 whitespace-pre-wrap text-muted">
            {e.texto}
          </div>
        )}
        <div className="tnum text-[11.5px] text-neutral-500">
          {dataHora(e.quando)}
        </div>
      </div>
    </li>
  );
}

function LinhaDoTempo({
  r,
  onRegistrou,
}: {
  r: Registro;
  onRegistrou: (x: Registro) => void;
}) {
  const opcoes = useOpcoes();
  const [texto, setTexto] = useState("");
  const [canal, setCanal] = useState("nota");
  const [direcao, setDirecao] = useState("saida");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function registrar() {
    if (!texto.trim()) return;
    setSalvando(true);
    setErro(null);
    try {
      onRegistrou(
        await api.crmRegistrar(
          r.id,
          texto.trim(),
          canal,
          canal === "nota" ? undefined : direcao,
        ),
      );
      setTexto("");
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Bloco titulo={`Linha do tempo (${r.linha_do_tempo.length})`}>
      {r.tipo === "negocio" && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <select
            className="input !w-auto !min-h-[32px] !py-[3px] !text-[13px]"
            aria-label="canal"
            value={canal}
            onChange={(e) => setCanal(e.target.value)}
          >
            {Object.entries(opcoes?.canal ?? { nota: "nota" }).map(
              ([v, rot]) => (
                <option key={v} value={v}>
                  {rot}
                </option>
              ),
            )}
          </select>
          {canal !== "nota" && (
            <select
              className="input !w-auto !min-h-[32px] !py-[3px] !text-[13px]"
              aria-label="direção"
              value={direcao}
              onChange={(e) => setDirecao(e.target.value)}
            >
              <option value="saida">eu fiz</option>
              <option value="entrada">recebi</option>
            </select>
          )}
          <input
            className="input !min-h-[32px] min-w-[200px] flex-1 !py-[3px] !text-[13px]"
            placeholder={canal === "nota" ? "anotar…" : "o que aconteceu…"}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void registrar()}
          />
          <button
            type="button"
            className="btn btn-secondary !min-h-[32px] !text-[13px]"
            disabled={salvando || !texto.trim()}
            onClick={registrar}
          >
            registrar
          </button>
          {erro && (
            <span className="w-full text-[12.5px] text-[#e07f86]">{erro}</span>
          )}
        </div>
      )}
      {r.linha_do_tempo.length === 0 ? (
        <p className="m-0 text-[13px] text-neutral-500">
          nada registrado ainda
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-[10px] p-0">
          {r.linha_do_tempo.map((e, i) => (
            <Evento
              key={`${e.tipo}-${e.quando}-${i}`}
              e={e}
              mostrarNegocio={r.tipo !== "negocio"}
            />
          ))}
        </ul>
      )}
      {r.tipo !== "negocio" && (
        <p className="mt-2 text-[12px] text-neutral-500">
          Registre contatos na ficha do negócio.
        </p>
      )}
    </Bloco>
  );
}
