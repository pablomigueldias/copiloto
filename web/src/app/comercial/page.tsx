"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { FichaCrm } from "@/components/comercial/FichaCrm";
import {
  Pilula,
  TelaCrm,
  brl,
  dataCurta,
  useOpcoes,
} from "@/components/comercial/crm";
import { Erro, Numero } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import type { PainelCrm, TipoRegistro } from "@/lib/tipos";

// A visão geral do CRM, como a do prospector: o funil em valor e quantidade,
// o que está para fazer (e o que atrasou), e a carteira.

function Secao({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="m-0 text-[15px] uppercase tracking-[0.08em] text-neutral-400">
        {titulo}
      </h2>
      {children}
    </section>
  );
}

export default function VisaoGeral() {
  const [p, setP] = useState<PainelCrm | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ficha, setFicha] = useState<{ tipo: TipoRegistro; id: number } | null>(
    null,
  );
  const opcoes = useOpcoes();

  const carregar = useCallback(() => {
    api
      .crmPainel()
      .then((x) => {
        setP(x);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, []);
  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const maxTotal = Math.max(1, ...(p?.por_estagio.map((e) => e.total) ?? [1]));

  return (
    <TelaCrm
      secao="Visão geral"
      acoes={
        <Link href="/comercial/base" className="btn btn-secondary">
          trazer clínicas da base
        </Link>
      }
    >
      {erro && <Erro>Não consegui carregar o painel: {erro}</Erro>}
      {!p ? (
        !erro && (
          <div className="h-48 animate-pulse rounded-[12px] bg-surface" />
        )
      ) : (
        <div className="flex flex-col gap-8">
          <Secao titulo="Pipeline">
            <div className="card grid grid-cols-2 gap-6 md:grid-cols-4">
              <Numero valor={p.negocios_abertos} rotulo="negócios abertos" />
              <Numero valor={brl(p.valor_aberto)} rotulo="valor em aberto" />
              <Numero
                valor={p.ganhos}
                rotulo={`ganhos · ${brl(p.valor_ganho)}`}
                cor="text-[#79c98a]"
              />
              <Numero valor={p.perdidos} rotulo="perdidos" />
            </div>
            <div className="card flex flex-col gap-[10px]">
              {p.por_estagio.map((e) => (
                <Link
                  key={e.estagio}
                  href={`/comercial/negocios?estagio=${e.estagio}`}
                  className="grid grid-cols-[110px_1fr_150px] items-center gap-3 text-[13.5px] text-text no-underline hover:text-accent"
                >
                  <Pilula valor={e.estagio}>{e.rotulo}</Pilula>
                  <div className="h-[8px] overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
                    <div
                      className="h-full rounded-full bg-accent-600"
                      style={{ width: `${(e.total / maxTotal) * 100}%` }}
                    />
                  </div>
                  <div className="tnum text-right text-muted">
                    {e.total} · {brl(e.valor)}
                  </div>
                </Link>
              ))}
            </div>
          </Secao>

          <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
            <Secao titulo="Atividades">
              <div className="card grid grid-cols-3 gap-6">
                <Numero valor={p.tarefas_abertas} rotulo="abertas" />
                <Numero valor={p.tarefas_hoje} rotulo="para hoje" />
                <Numero
                  valor={p.tarefas_atrasadas}
                  rotulo="atrasadas"
                  cor={p.tarefas_atrasadas ? "text-[#e07f86]" : undefined}
                />
              </div>
              <div className="card">
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="card-kicker text-neutral-400">próximas</span>
                  <Link
                    href="/comercial/atividades"
                    className="text-[12.5px] no-underline hover:underline"
                  >
                    todas →
                  </Link>
                </div>
                {p.proximas.length === 0 ? (
                  <p className="m-0 text-[13.5px] text-neutral-500">
                    Nada aberto. Bom sinal, ou falta prospectar.
                  </p>
                ) : (
                  <ul className="m-0 flex list-none flex-col p-0">
                    {p.proximas.map((a) => (
                      <li
                        key={a.id}
                        className="border-t border-divider first:border-t-0"
                      >
                        <button
                          type="button"
                          onClick={() =>
                            setFicha({ tipo: "negocio", id: a.lead_id })
                          }
                          className="flex w-full items-center gap-3 py-[8px] text-left text-[13.5px] hover:text-accent"
                        >
                          <span
                            className={`tnum w-[46px] flex-none ${a.atrasada ? "text-[#e07f86]" : "text-neutral-400"}`}
                          >
                            {dataCurta(a.vence_em)}
                          </span>
                          <span className="flex-none text-muted">
                            {opcoes?.tipo_tarefa[a.tipo] ?? a.tipo}
                          </span>
                          <span className="truncate text-text">
                            {a.descricao ? `${a.descricao} · ` : ""}
                            {a.empresa_nome ?? a.negocio_nome}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Secao>

            <Secao titulo="Carteira">
              <div className="card grid grid-cols-3 gap-6">
                <Numero valor={p.empresas} rotulo="empresas" />
                <Numero valor={p.clientes} rotulo="clientes" />
                <Numero valor={p.contatos} rotulo="contatos" />
              </div>
              <div className="card">
                <span className="card-kicker mb-2 block text-neutral-400">
                  por que perdemos
                </span>
                {p.motivos_perda.length === 0 ? (
                  <p className="m-0 text-[13.5px] text-neutral-500">
                    Nenhuma perda com motivo ainda.
                  </p>
                ) : (
                  <ul className="m-0 flex list-none flex-col gap-[6px] p-0 text-[13.5px]">
                    {p.motivos_perda.map((m) => (
                      <li key={m.motivo} className="flex justify-between gap-3">
                        <span className="text-text">{m.motivo}</span>
                        <span className="tnum text-neutral-400">{m.total}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Secao>
          </div>
        </div>
      )}
      {ficha && (
        <FichaCrm
          tipo={ficha.tipo}
          id={ficha.id}
          onFechar={() => setFicha(null)}
          onMudou={carregar}
        />
      )}
    </TelaCrm>
  );
}
