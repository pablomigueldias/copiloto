"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { FichaCrm } from "@/components/comercial/FichaCrm";
import { FormCrm } from "@/components/comercial/FormCrm";
import {
  BarraLista,
  Celula,
  Pilula,
  Segmentos,
  TelaCrm,
  brl,
  dataCurta,
  td,
  th,
  useAtrasado,
  useOpcoes,
} from "@/components/comercial/crm";
import { Erro, Numero, Vazio } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type { NegocioCrm, TipoRegistro } from "@/lib/tipos";

// Os negócios (o lead do CRM) por estágio. Arrastar muda o estágio **pela
// regra de código** (`leads.mover`): a coluna que não é destino possível fica
// apagada enquanto se arrasta, e perdido pede o motivo (Fase 1, passo 7.1).

const ABERTOS = ["prospect", "contatado", "respondeu", "reuniao", "proposta"];
const ENCERRADOS = ["ganho", "nao_agora", "perdido"];
const ORDEM = [...ABERTOS, ...ENCERRADOS];

/** Uma coluna do kanban: recebe o cartão solto e diz se é destino possível. */
function Coluna({
  estagio,
  arrastando,
  alvo,
  setAlvo,
  onSoltar,
  compacta,
  children,
}: {
  estagio: string;
  arrastando: NegocioCrm | null;
  alvo: string | null;
  setAlvo: (f: (a: string | null) => string | null) => void;
  onSoltar: (id: number, estagio: string) => void;
  compacta?: boolean;
  children: React.ReactNode;
}) {
  const destino = arrastando ? arrastando.pode_ir.includes(estagio) : true;
  return (
    <section
      aria-label={estagio}
      // A coluna proibida também aceita o soltar: é para dizer por que não, em
      // vez de o cartão voltar calado.
      onDragOver={(ev) => {
        ev.preventDefault();
        if (destino) setAlvo(() => estagio);
      }}
      onDragLeave={() => setAlvo((a) => (a === estagio ? null : a))}
      onDrop={(ev) => {
        ev.preventDefault();
        setAlvo(() => null);
        const id = Number(ev.dataTransfer.getData("text/plain"));
        if (id) onSoltar(id, estagio);
      }}
      className={`flex min-w-0 flex-col gap-[10px] rounded-[12px] p-2 transition-[background-color,opacity] ${
        compacta ? "border border-dashed border-divider" : ""
      } ${alvo === estagio ? "bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)]" : ""} ${
        arrastando && !destino && arrastando.estagio !== estagio
          ? "opacity-35"
          : ""
      }`}
    >
      {children}
    </section>
  );
}

type Vista = "kanban" | "lista";

function Cartao({
  n,
  arrastando,
  onArrastar,
  onAbrir,
  onValor,
  rotuloTarefa,
}: {
  n: NegocioCrm;
  arrastando: boolean;
  onArrastar: (n: NegocioCrm | null) => void;
  onAbrir: () => void;
  onValor: (v: string | boolean | null) => Promise<unknown>;
  rotuloTarefa: string;
}) {
  return (
    <article
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(n.id));
        e.dataTransfer.effectAllowed = "move";
        onArrastar(n);
      }}
      onDragEnd={() => onArrastar(null)}
      onClick={onAbrir}
      className={`card elev-sm flex cursor-pointer flex-col gap-[5px] !p-3 transition-colors hover:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] ${
        arrastando ? "opacity-40" : ""
      }`}
    >
      <div className="text-[13.5px] font-medium leading-snug text-text">
        {n.nome}
      </div>
      {(n.contato_nome || (n.empresa_nome && n.empresa_nome !== n.nome)) && (
        <div className="truncate text-[12px] text-muted">
          {[n.empresa_nome !== n.nome ? n.empresa_nome : null, n.contato_nome]
            .filter(Boolean)
            .join(" · ")}
        </div>
      )}
      <div className="flex items-center justify-between gap-2 text-[12.5px]">
        <span className="tnum whitespace-nowrap font-medium">
          <Celula
            valor={n.valor_estimado}
            exibicao={n.valor_estimado != null ? brl(n.valor_estimado) : ""}
            tipo="numero"
            vazio="+ valor"
            onSalvar={onValor}
          />
        </span>
        {n.tarefas_abertas > 0 && (
          <span className="tnum text-neutral-400">{rotuloTarefa}</span>
        )}
      </div>
      {n.proxima_acao && (
        <div className="line-clamp-2 text-[11.5px] text-neutral-500">
          {n.proxima_em ? `${dataCurta(n.proxima_em)} · ` : ""}
          {n.proxima_acao}
        </div>
      )}
      {n.motivo_perda && (
        <div className="line-clamp-2 text-[11.5px] text-[#e07f86]">
          {n.motivo_perda}
        </div>
      )}
    </article>
  );
}

export default function Pagina() {
  // `useSearchParams` pede um Suspense em volta: sem ele o build não prerenderiza.
  return (
    <Suspense>
      <Negocios />
    </Suspense>
  );
}

function Negocios() {
  const opcoes = useOpcoes();
  // `?abrir=12` (vindo da base ou da página do lead) abre a ficha; `?estagio=x`
  // (vindo do painel) mostra a lista daquele estágio.
  const q = useSearchParams();
  const [vista, setVista] = useState<Vista>(
    q.get("estagio") ? "lista" : "kanban",
  );
  const [busca, setBusca] = useState("");
  const [estagio, setEstagio] = useState(q.get("estagio") ?? "");
  const [negocios, setNegocios] = useState<NegocioCrm[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ficha, setFicha] = useState<{ tipo: TipoRegistro; id: number } | null>(
    () =>
      Number(q.get("abrir"))
        ? { tipo: "negocio", id: Number(q.get("abrir")) }
        : null,
  );
  const [novo, setNovo] = useState(false);
  const [arrastando, setArrastando] = useState<NegocioCrm | null>(null);
  const [alvo, setAlvo] = useState<string | null>(null);
  const [perda, setPerda] = useState<NegocioCrm | null>(null);
  const [excluir, setExcluir] = useState<NegocioCrm | null>(null);
  const termo = useAtrasado(busca);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .crmNegocios({ busca: termo })
      .then((n) => {
        setNegocios(n);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, [termo]);
  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const rotulo = (e: string) => opcoes?.estagio[e] ?? e;
  const abertos = useMemo(
    () => (negocios ?? []).filter((n) => ABERTOS.includes(n.estagio)),
    [negocios],
  );

  async function mover(n: NegocioCrm, para: string, motivo?: string) {
    if (para === n.estagio) return;
    if (!n.pode_ir.includes(para)) {
      falhou(
        `${rotulo(n.estagio)} → ${rotulo(para)} não é permitido: o funil anda um passo por vez`,
      );
      return;
    }
    if (para === "perdido" && !motivo) {
      setPerda(n);
      return;
    }
    // Otimista: o cartão muda de coluna na hora; o servidor confirma ou desfaz.
    setNegocios(
      (l) => l?.map((x) => (x.id === n.id ? { ...x, estagio: para } : x)) ?? l,
    );
    try {
      await api.crmMover(n.id, para, motivo);
      ok(`${n.nome}: ${rotulo(para)}`);
    } catch (e) {
      falhou("Não mudei o estágio", e);
    }
    carregar();
  }

  const valor = (id: number) => async (v: string | boolean | null) => {
    await api.crmEditar("negocio", id, { valor_estimado: v });
    carregar();
  };

  const visiveis = (negocios ?? []).filter(
    (n) => !estagio || n.estagio === estagio,
  );
  const coluna = {
    arrastando,
    alvo,
    setAlvo,
    onSoltar: (id: number, para: string) => {
      const n = negocios?.find((x) => x.id === id);
      if (n) void mover(n, para);
    },
  };

  return (
    <TelaCrm
      secao="Negócios"
      acoes={
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setNovo(true)}
        >
          + novo negócio
        </button>
      }
    >
      {negocios && negocios.length > 0 && (
        <div className="card mb-5 grid grid-cols-2 gap-6 md:grid-cols-4">
          <Numero valor={abertos.length} rotulo="em andamento" />
          <Numero
            valor={brl(
              abertos.reduce((s, n) => s + (n.valor_estimado ?? 0), 0),
            )}
            rotulo="valor em andamento"
          />
          <Numero
            valor={negocios.filter((n) => n.estagio === "ganho").length}
            rotulo="ganhos"
            cor="text-[#79c98a]"
          />
          <Numero
            valor={negocios.filter((n) => n.estagio === "nao_agora").length}
            rotulo="não agora (voltam em 90 d)"
          />
        </div>
      )}

      <BarraLista
        busca={busca}
        onBusca={setBusca}
        filtros={
          vista === "lista" && (
            <select
              className="input !w-auto"
              aria-label="estágio"
              value={estagio}
              onChange={(e) => setEstagio(e.target.value)}
            >
              <option value="">estágio: todos</option>
              {ORDEM.map((e) => (
                <option key={e} value={e}>
                  {rotulo(e)}
                </option>
              ))}
            </select>
          )
        }
        acoes={
          <Segmentos
            rotulo="vista"
            valor={vista}
            onMudar={setVista}
            opcoes={[
              { valor: "kanban", rotulo: "Kanban" },
              { valor: "lista", rotulo: "Lista" },
            ]}
          />
        }
      />

      {erro && <Erro>Não consegui carregar os negócios: {erro}</Erro>}
      {negocios && negocios.length === 0 && !termo ? (
        <Vazio
          titulo="Nenhum negócio ainda"
          acao={{ href: "/comercial/base", rotulo: "Trazer clínicas da base" }}
        >
          O negócio nasce quando uma clínica vem da base, ou à mão, numa
          indicação.
        </Vazio>
      ) : negocios && vista === "kanban" ? (
        <div
          className="grid gap-3 overflow-x-auto pb-4"
          style={{
            gridTemplateColumns:
              "repeat(5, minmax(150px, 1fr)) minmax(150px, 0.9fr)",
          }}
        >
          {ABERTOS.map((e) => {
            const itens = visiveis.filter((n) => n.estagio === e);
            const soma = itens.reduce((s, n) => s + (n.valor_estimado ?? 0), 0);
            return (
              <Coluna key={e} estagio={e} {...coluna}>
                <div className="flex items-center justify-between px-1">
                  <Pilula valor={e}>{rotulo(e)}</Pilula>
                  <span className="tnum text-[12px] text-neutral-500">
                    {itens.length}
                  </span>
                </div>
                <div className="tnum -mt-1 px-1 text-[11.5px] text-neutral-500">
                  {soma ? brl(soma) : " "}
                </div>
                {itens.map((n) => (
                  <Cartao
                    key={n.id}
                    n={n}
                    arrastando={arrastando?.id === n.id}
                    onArrastar={setArrastando}
                    onAbrir={() => setFicha({ tipo: "negocio", id: n.id })}
                    onValor={valor(n.id)}
                    rotuloTarefa={`${n.tarefas_abertas} tarefa${n.tarefas_abertas > 1 ? "s" : ""}`}
                  />
                ))}
              </Coluna>
            );
          })}
          {/* Os encerrados numa coluna só: cabem na tela, e continuam sendo
              destino de arrastar (ganhou, "não agora", perdeu). */}
          <div className="flex flex-col gap-3">
            {ENCERRADOS.map((e) => {
              const itens = visiveis.filter((n) => n.estagio === e);
              return (
                <Coluna key={e} estagio={e} {...coluna} compacta>
                  <div className="flex items-center justify-between px-1">
                    <Pilula valor={e}>{rotulo(e)}</Pilula>
                    <span className="tnum text-[12px] text-neutral-500">
                      {itens.length}
                    </span>
                  </div>
                  <ul className="m-0 flex max-h-[180px] list-none flex-col overflow-y-auto p-0">
                    {itens.map((n) => (
                      <li key={n.id}>
                        <button
                          type="button"
                          draggable
                          onDragStart={(ev) => {
                            ev.dataTransfer.setData("text/plain", String(n.id));
                            setArrastando(n);
                          }}
                          onDragEnd={() => setArrastando(null)}
                          onClick={() =>
                            setFicha({ tipo: "negocio", id: n.id })
                          }
                          className="w-full truncate rounded-[6px] px-1 py-[3px] text-left text-[12.5px] text-muted hover:bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)] hover:text-text"
                          title={n.motivo_perda ?? undefined}
                        >
                          {n.nome}
                        </button>
                      </li>
                    ))}
                  </ul>
                </Coluna>
              );
            })}
          </div>
        </div>
      ) : negocios ? (
        <div className="card overflow-x-auto !p-0">
          <table className="w-full border-collapse text-[13.5px]">
            <thead>
              <tr className="card-kicker border-b border-divider text-neutral-500">
                <th className={`${th} pl-4`}>Negócio</th>
                <th className={th}>Estágio</th>
                <th className={th}>Empresa · contato</th>
                <th className={`${th} text-right`}>Valor</th>
                <th className={th}>Próxima ação</th>
                <th className={th}>Origem</th>
                <th className={`${th} pr-4`} />
              </tr>
            </thead>
            <tbody>
              {visiveis.map((n) => (
                <tr
                  key={n.id}
                  onClick={() => setFicha({ tipo: "negocio", id: n.id })}
                  className="cursor-pointer border-t border-divider first:border-t-0 hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                >
                  <td className={`${td} pl-4 font-medium text-text`}>
                    {n.nome}
                  </td>
                  <td className={td}>
                    <Celula
                      valor={n.estagio}
                      exibicao={rotulo(n.estagio)}
                      tipo="opcao"
                      opcoes={[n.estagio, ...n.pode_ir].map((e) => ({
                        valor: e,
                        rotulo: rotulo(e),
                      }))}
                      onSalvar={(v) => mover(n, String(v))}
                    />
                  </td>
                  <td className={`${td} text-muted`}>
                    {[
                      n.empresa_nome !== n.nome ? n.empresa_nome : null,
                      n.contato_nome,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </td>
                  <td className={`${td} tnum text-right`}>
                    <Celula
                      valor={n.valor_estimado}
                      exibicao={
                        n.valor_estimado != null ? brl(n.valor_estimado) : ""
                      }
                      tipo="numero"
                      onSalvar={valor(n.id)}
                    />
                  </td>
                  <td className={`${td} max-w-[280px] text-muted`}>
                    <span className="line-clamp-2">
                      {n.proxima_em ? `${dataCurta(n.proxima_em)} · ` : ""}
                      {n.proxima_acao ?? "—"}
                    </span>
                  </td>
                  <td className={`${td} text-neutral-400`}>
                    {opcoes?.origem[n.origem] ?? n.origem}
                  </td>
                  <td className={`${td} pr-4 text-right`}>
                    <button
                      type="button"
                      className="text-[12px] text-neutral-500 hover:text-[#e07f86]"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        setExcluir(n);
                      }}
                    >
                      excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {ficha && (
        <FichaCrm
          tipo={ficha.tipo}
          id={ficha.id}
          onFechar={() => setFicha(null)}
          onMudou={carregar}
        />
      )}
      {novo && (
        <FormCrm
          tipo="negocio"
          onFechar={() => setNovo(false)}
          onSalvo={(id) => {
            carregar();
            setFicha({ tipo: "negocio", id });
          }}
        />
      )}
      {perda && (
        <Dialogo
          titulo={`Por que perdeu ${perda.nome}?`}
          descricao="O motivo da perda é o dado que ensina o preço e a oferta."
          confirmar="marcar perdido"
          multilinha
          placeholder="ex.: já usa outro sistema; achou caro; não respondeu ao lembrete"
          onConfirmar={(motivo) => {
            const n = perda;
            setPerda(null);
            if (motivo.trim()) void mover(n, "perdido", motivo.trim());
            else falhou("Perdido precisa de motivo");
          }}
          onCancelar={() => setPerda(null)}
        />
      )}
      {excluir && (
        <Dialogo
          titulo="Excluir negócio"
          descricao={`Excluir "${excluir.nome}"? Só dá para excluir o que ainda não recebeu contato; o resto vai para "perdido".`}
          confirmar="excluir"
          perigo
          onConfirmar={async () => {
            const alvo_ = excluir;
            setExcluir(null);
            try {
              await api.crmExcluir("negocio", alvo_.id);
              ok(`${alvo_.nome} excluído`);
              carregar();
            } catch (e) {
              falhou("Não excluí", e);
            }
          }}
          onCancelar={() => setExcluir(null)}
        />
      )}
      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </TelaCrm>
  );
}
