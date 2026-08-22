"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Cabecalho, Erro, Vazio } from "@/components/ui";
import { api } from "@/lib/api";

type Trecho = {
  id: string;
  fonte_tipo: string;
  fonte_ref: string;
  titulo: string | null;
  conteudo: string;
  score: number;
  origem: string;
  distancia: number | null;
};

function Busca() {
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [trechos, setTrechos] = useState<Trecho[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [buscando, setBuscando] = useState(false);

  const buscar = async (termo: string) => {
    if (termo.trim().length < 3) return;
    setBuscando(true);
    setErro(null);
    try {
      const r = (await api.buscarConhecimento(termo)) as {
        trechos: Trecho[];
      };
      setTrechos(r.trechos ?? []);
    } catch (e) {
      setErro(String((e as Error).message ?? e));
    } finally {
      setBuscando(false);
    }
  };

  // `?q=` vindo da caixa de busca do painel. O efeito não escreve estado
  // direto: só o `.then` escreve, depois que a resposta chega.
  useEffect(() => {
    const inicial = params.get("q");
    if (!inicial || inicial.trim().length < 3) return;
    let vivo = true;
    api
      .buscarConhecimento(inicial)
      .then((r) => vivo && setTrechos(((r as { trechos: Trecho[] }).trechos) ?? []))
      .catch((e) => vivo && setErro(String((e as Error).message ?? e)));
    return () => {
      vivo = false;
    };
  }, [params]);

  return (
    <div className="max-w-[900px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Conhecimento</Cabecalho>
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">
        O que eu já estudei
      </h1>
      <p className="m-0 mb-6 max-w-[62ch] text-[15px] text-muted">
        Busca híbrida — vetorial e full-text fundidos por Reciprocal Rank
        Fusion — sobre as notas, PDFs e READMEs indexados. Quando o melhor
        trecho passa do corte de distância, a resposta é &ldquo;não está nas
        minhas notas&rdquo;, e isso é resultado, não falha.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void buscar(q);
        }}
        className="mb-8 flex max-w-[620px] items-stretch gap-2"
      >
        <input
          className="input min-h-[40px] flex-1 text-[15px]"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="o que eu estudei sobre…?"
        />
        <button
          type="submit"
          disabled={buscando}
          className="btn btn-primary px-4 py-[9px]"
        >
          {buscando ? "…" : "buscar"}
        </button>
      </form>

      {erro && <Erro>{erro}</Erro>}

      {trechos?.length === 0 && (
        <Vazio titulo="Nada no índice para isso">
          Nenhum trecho passou do corte. Se o assunto deveria estar lá, o índice
          pode estar desatualizado — rode a ingestão.
        </Vazio>
      )}

      <div className="flex flex-col gap-3">
        {trechos?.map((t) => (
          <article key={t.id} className="card elev-sm">
            <div className="mb-2 flex flex-wrap items-baseline gap-3">
              <span className="card-kicker">{t.fonte_tipo}</span>
              <span className="text-[13.5px] text-accent-300">
                {t.titulo ?? t.fonte_ref}
              </span>
              <span className="tnum ml-auto text-[11.5px] text-neutral-600">
                {t.origem}
                {t.distancia !== null
                  ? ` · distância ${t.distancia.toFixed(3)}`
                  : ""}
              </span>
            </div>
            <p className="m-0 whitespace-pre-line text-[14px] leading-[1.6] text-muted">
              {t.conteudo}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-8 text-[13px] text-neutral-500">…</div>}>
      <Busca />
    </Suspense>
  );
}
