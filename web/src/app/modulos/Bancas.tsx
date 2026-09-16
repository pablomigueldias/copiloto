"use client";

import { useCallback, useEffect, useState } from "react";

import { plural } from "@/components/ui";
import { api } from "@/lib/api";
import type { Banca } from "@/lib/tipos";

/**
 * A tira de bancas no topo de Módulos — e o botão que pausa uma delas.
 *
 * Existe porque eu estudo para uma banca por vez e o acervo não. Quando o foco
 * muda de concurso, a repetição espaçada continua devolvendo todo dia a prova
 * que eu não vou mais fazer, e a única saída antes disto era apagar o módulo,
 * que leva junto o histórico — meses de agendamento que não se refazem.
 *
 * Pausar é a terceira opção: a banca some da fila do dia e dos contadores, o
 * acervo fica intacto e o botão desfaz num clique. Por ser reversível e não
 * destrutivo, ele **não pergunta nada** antes — ao contrário de apagar módulo,
 * que exige confirmação com o número de questões na mão.
 *
 * A linha "Sem banca (inéditas)" vem sem `id`: questão que eu escrevi não
 * pertence a concurso nenhum, não se pausa, e por isso não ganha botão.
 */
export function Bancas({
  onMudou,
  onErro,
}: {
  onMudou: (mensagem: string) => void;
  onErro: (mensagem: string) => void;
}) {
  const [bancas, setBancas] = useState<Banca[] | null>(null);
  const [mexendo, setMexendo] = useState<string | null>(null);

  const carregar = useCallback(() => {
    api
      .bancas()
      .then(setBancas)
      .catch((e) => onErro(String((e as Error).message ?? e)));
  }, [onErro]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  /** Um clique para "agora é esta". Desfaz em `retomarTodas`. */
  const focar = async (b: Banca) => {
    if (!b.id || mexendo) return;
    setMexendo(b.id);
    try {
      const r = await api.focarBanca(b.id);
      onMudou(
        r.bancas_pausadas === 0
          ? `${r.banca} já era a única em estudo`
          : `Foco em ${r.banca} — ${plural(r.bancas_pausadas, "banca pausada", "bancas pausadas")}, ${r.questoes_pausadas} questões fora da fila`,
      );
      carregar();
    } catch (e) {
      onErro(String((e as Error).message ?? e));
    } finally {
      setMexendo(null);
    }
  };

  const retomarTodas = async () => {
    if (mexendo) return;
    setMexendo("todas");
    try {
      const r = await api.retomarTodasBancas();
      onMudou(
        `${plural(r.bancas_retomadas, "banca de volta", "bancas de volta")} ao estudo, com o histórico`,
      );
      carregar();
    } catch (e) {
      onErro(String((e as Error).message ?? e));
    } finally {
      setMexendo(null);
    }
  };

  const alternar = async (b: Banca) => {
    if (!b.id || mexendo) return;
    setMexendo(b.id);
    try {
      await api.editarBanca(b.id, { ativa: !b.ativa });
      onMudou(
        b.ativa
          ? `${b.nome} pausada — ${plural(b.questoes, "questão sai", "questões saem")} da fila, sem perder o histórico`
          : `${b.nome} de volta ao estudo`,
      );
      // Recarrega a própria tira; os cards e a sidebar vêm do `MUTOU` que o
      // cliente da API dispara sozinho depois de toda escrita — e eles foram
      // calculados com a banca no outro estado.
      carregar();
    } catch (e) {
      onErro(String((e as Error).message ?? e));
    } finally {
      setMexendo(null);
    }
  };

  if (!bancas || bancas.length === 0) return null;

  const pausadas = bancas.filter((b) => !b.ativa);
  // As sem id (inéditas) não contam: elas não se pausam, então "focar" não
  // mudaria nada em relação a elas.
  const ativas = bancas.filter((b) => b.ativa && b.id).length;

  return (
    <section className="mb-7">
      <div className="mb-3 flex items-baseline gap-3">
        <h2 className="m-0 text-[15px] font-medium">Bancas</h2>
        <span className="h-px flex-1 bg-divider" />
        <span className="tnum flex-none text-[12px] text-neutral-500">
          {pausadas.length
            ? `${plural(pausadas.length, "pausada", "pausadas")} · ${plural(
                pausadas.reduce((s, b) => s + b.questoes, 0),
                "questão fora da fila",
                "questões fora da fila",
              )}`
            : "todas em estudo"}
        </span>
        {/* O desfazer do "focar". Sem ele, uma ação que pausa nove bancas de
            uma vez custaria nove cliques para voltar atrás. */}
        {pausadas.length > 1 && (
          <button
            type="button"
            onClick={retomarTodas}
            disabled={mexendo !== null}
            className="btn btn-ghost flex-none px-2 py-[2px] text-[12px]"
          >
            {mexendo === "todas" ? "…" : "retomar todas"}
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {bancas.map((b) => (
          <div
            key={b.id ?? "sem-banca"}
            className={`flex items-center gap-[10px] rounded-[10px] border px-[12px] py-[7px] transition-colors ${
              b.ativa
                ? "border-[color-mix(in_srgb,var(--color-accent)_35%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_7%,transparent)]"
                : "border-divider bg-transparent opacity-55"
            }`}
          >
            <span className="text-[13.5px]">{b.nome}</span>
            <span className="tnum text-[12px] text-neutral-500">
              {b.questoes}
              {b.ativa && b.hoje > 0 && (
                <span className="text-accent"> · {b.hoje} hoje</span>
              )}
            </span>
            {b.id ? (
              <>
                <button
                  type="button"
                  onClick={() => alternar(b)}
                  disabled={mexendo !== null}
                  className="btn btn-ghost px-[6px] py-[2px] text-[12px]"
                  title={
                    b.ativa
                      ? "Tira da fila do dia. O acervo e o histórico ficam."
                      : "Devolve à fila do dia, com o histórico inteiro."
                  }
                >
                  {mexendo === b.id ? "…" : b.ativa ? "pausar" : "retomar"}
                </button>
                {/* Só aparece quando há o que pausar: numa tela onde uma banca
                    já é a única ativa, "focar" não faria nada e mesmo assim
                    pediria um clique. */}
                {ativas > 1 && (
                  <button
                    type="button"
                    onClick={() => focar(b)}
                    disabled={mexendo !== null}
                    className="btn btn-ghost px-[6px] py-[2px] text-[12px] text-accent-300"
                    title="Deixa só esta banca em estudo e pausa as outras."
                  >
                    focar
                  </button>
                )}
              </>
            ) : (
              <span className="text-[11.5px] text-neutral-600">sempre ativas</span>
            )}
          </div>
        ))}
      </div>

      {pausadas.length > 0 && (
        <p className="m-0 mt-[10px] max-w-[70ch] text-[12.5px] leading-[1.55] text-neutral-500">
          Banca pausada sai da fila do dia e dos contadores dos módulos, e
          continua inteira no acervo — abrir o tópico mostra as questões, com
          gabarito e histórico. Retomar devolve tudo ao ponto em que parou.
        </p>
      )}
    </section>
  );
}
