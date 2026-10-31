"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Icone } from "@/components/icones";
import { AcaoReforco, GerarTodos, useAtualizarEnquantoGera } from "@/components/simulado/GerarReforco";
import { nota } from "@/components/simulado/Questao";
import { Cabecalho, Erro, plural } from "@/components/ui";
import { api, ApiErro } from "@/lib/api";
import type { EstadoSimulado, ReforcoResumo } from "@/lib/tipos";

function data(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function LinhaReforco({ r, onMudou }: { r: ReforcoResumo; onMudou: () => void }) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-divider py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="text-[15px]">{r.assunto}</div>
        <div className="mt-px text-[12px] text-neutral-500">
          {r.materia_nome}
          {r.grupo ? ` · ${r.grupo}` : ""} · {plural(r.erros_no_simulado, "erro", "erros")} no simulado
          {r.rodada > 1 ? ` · rodada ${r.rodada}` : ""}
        </div>
      </div>
      <AcaoReforco r={r} onMudou={onMudou} />
    </li>
  );
}

export default function Page() {
  const router = useRouter();
  const [estado, setEstado] = useState<EstadoSimulado | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [montando, setMontando] = useState(false);

  const carregar = useCallback(() => {
    api.simulado().then(setEstado).catch((e) => setErro(String(e.message ?? e)));
  }, []);
  useEffect(carregar, [carregar]);
  useAtualizarEnquantoGera(estado?.reforcos_pendentes, carregar);

  async function comecar() {
    setMontando(true);
    try {
      const s = await api.iniciarSimulado();
      router.push(`/simulado/prova?id=${s.id}`);
    } catch (e) {
      setErro(e instanceof ApiErro ? e.message : String(e));
      setMontando(false);
    }
  }

  if (erro) {
    return (
      <div className="px-[clamp(24px,4vw,56px)] py-[34px]">
        <Erro>{erro}</Erro>
      </div>
    );
  }
  if (!estado) {
    return <div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">carregando…</div>;
  }

  const proximo = (estado.historico[0]?.numero ?? 0) + 1;
  const total = estado.materias.reduce((s, m) => s + Math.min(m.questoes, m.estoque), 0);
  const aguardando = estado.reforcos_pendentes.filter((r) => r.estado === "aguardando_questoes");

  return (
    <div className="max-w-[860px] px-[clamp(24px,4vw,56px)] py-[34px]">
      <h1 className="m-0 mb-2 text-[clamp(28px,3.4vw,38px)] leading-[1.08] tracking-[-0.02em]">Simulado</h1>
      <p className="m-0 mb-8 max-w-[62ch] text-[14.5px] text-muted">
        A prova do Avança SP (CRECI-SP 01/2026, Analista de TI — Banco de Dados) no quadro do edital: 30 de
        Específicos, 10 de Matemática, 10 de Português e 10 de Inglês técnico, nessa ordem, no peso em que a
        banca costuma cobrar. Só entra assunto que está no programa do edital. Cada assunto errado vira um reforço de 5 questões, e o próximo simulado só abre
        depois de acertar {"≥"} 75% em cada um.
      </p>

      {estado.em_andamento && (
        <section className="mb-10">
          <Cabecalho>Em andamento</Cabecalho>
          <div className="card flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-[17px]">Simulado nº {estado.em_andamento.numero}</div>
              <div className="tnum mt-1 text-[13px] text-muted">
                {estado.em_andamento.respondidas} de {estado.em_andamento.total} marcadas · começou em{" "}
                {data(estado.em_andamento.iniciado_em)}
              </div>
            </div>
            <Link href={`/simulado/prova?id=${estado.em_andamento.id}`} className="btn btn-primary px-[18px] py-[10px]">
              Continuar a prova
              <Icone nome="seta" />
            </Link>
          </div>
        </section>
      )}

      {estado.reforcos_pendentes.length > 0 && (
        <section className="mb-10">
          <Cabecalho>Reforço antes do próximo simulado</Cabecalho>
          {aguardando.length > 0 && (
            <div className="mb-4 flex flex-col gap-3">
              <p className="m-0 max-w-[62ch] text-[13.5px] text-muted">
                {plural(aguardando.length, "assunto ainda não tem", "assuntos ainda não têm")} questões. Elas são
                escritas sob medida para o seu erro, fora do estoque da prova, com o gabarito conferido — por
                isso levam alguns minutos cada.
              </p>
              <GerarTodos reforcos={estado.reforcos_pendentes} onMudou={carregar} />
            </div>
          )}
          <ul className="card m-0 list-none py-1">
            {estado.reforcos_pendentes.map((r) => (
              <LinhaReforco key={r.id} r={r} onMudou={carregar} />
            ))}
          </ul>
        </section>
      )}

      {estado.liberado && (
        <section className="mb-10">
          <Cabecalho>Simulado nº {proximo}</Cabecalho>
          <div className="card">
            <table className="tnum mb-5 w-full border-collapse text-[14px]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-[0.08em] text-neutral-500">
                  <th className="pb-2 font-normal">Matéria</th>
                  <th className="pb-2 text-right font-normal">No edital</th>
                  <th className="pb-2 text-right font-normal">No estoque</th>
                </tr>
              </thead>
              <tbody>
                {estado.materias.map((m) => (
                  <tr key={m.chave} className="border-t border-divider">
                    <td className="py-2">{m.nome}</td>
                    <td className="py-2 text-right">{m.questoes}</td>
                    <td className={`py-2 text-right ${m.estoque < m.questoes ? "text-accent-300" : "text-muted"}`}>
                      {m.estoque}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="m-0 mb-5 max-w-[62ch] text-[13px] text-muted">
              {total} questões, sem gabarito até entregar. Nota pela fórmula do edital (item 12.3): P = 100/Q
              × acertos; habilitado com {estado.nota_minima} ou mais (item 12.6). Em branco conta como erro. A
              prova real dá 4 h, incluída a discursiva, que este simulado não cobre.
              {estado.historico.length > 0 &&
                " Os assuntos que você errou nos últimos simulados voltam em até 30% das vagas."}
            </p>
            <button
              type="button"
              onClick={comecar}
              disabled={montando}
              className="btn btn-primary px-[18px] py-[10px] text-[15px]"
            >
              {montando ? "montando…" : "Começar o simulado"}
              <Icone nome="seta" />
            </button>
          </div>
        </section>
      )}

      {estado.historico.length > 0 && (
        <section className="mb-10">
          <Cabecalho>Simulados feitos</Cabecalho>
          <ul className="card m-0 list-none py-1">
            {estado.historico.map((s) => (
              <li key={s.id} className="border-b border-divider last:border-b-0">
                <Link
                  href={`/simulado/resultado?id=${s.id}`}
                  className="flex items-center gap-4 py-3 text-text no-underline hover:text-accent"
                >
                  <span className="w-[110px] text-[14px]">nº {s.numero}</span>
                  <span className="tnum text-[13px] text-neutral-500">{s.finalizado_em ? data(s.finalizado_em) : ""}</span>
                  <span className="tnum ml-auto text-[13px] text-muted">
                    {s.acertos}/{s.total}
                  </span>
                  <span className="tnum w-[64px] text-right text-[16px] font-medium">{nota(s.nota)}</span>
                  <span className={`w-[96px] text-right text-[12px] ${s.habilitado ? "text-accent" : "text-neutral-500"}`}>
                    {s.habilitado ? "habilitado" : "abaixo de 50"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {estado.reforcos_concluidos.length > 0 && (
        <section>
          <Cabecalho>Reforços concluídos</Cabecalho>
          <ul className="card m-0 list-none py-1">
            {estado.reforcos_concluidos.map((r) => (
              <li key={r.id} className="flex items-center gap-4 border-b border-divider py-[10px] text-[14px] last:border-b-0">
                <span className="min-w-0 flex-1 truncate">{r.assunto}</span>
                <span className="text-[12px] text-neutral-500">rodada {r.rodada}</span>
                <span className="tnum w-[40px] text-right text-muted">
                  {r.acertos}/{r.total}
                </span>
                <span className={`w-[80px] text-right text-[12px] ${r.estado === "aprovado" ? "text-accent" : "text-neutral-500"}`}>
                  {r.estado}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
