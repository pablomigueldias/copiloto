"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { Icone } from "@/components/icones";
import { CorpoQuestao, Corrigida, Opcao, PorQue } from "@/components/simulado/Questao";
import { Erro } from "@/components/ui";
import { api } from "@/lib/api";
import type { ReforcoDetalhe } from "@/lib/tipos";

/**
 * O reforço corrige na hora. No simulado o gabarito espera a entrega porque
 * ali se mede; aqui se aprende, e o porquê serve mais logo depois do erro.
 */
function Reforco() {
  const id = useSearchParams().get("id") ?? "";
  const [r, setR] = useState<ReforcoDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [i, setI] = useState(0);
  const [escolhida, setEscolhida] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api
      .reforco(id)
      .then((d) => {
        setR(d);
        const aberta = d.itens.findIndex((it) => !it.resposta);
        setI(aberta === -1 ? d.itens.length : aberta);
      })
      .catch((e) => setErro(String(e.message ?? e)));
  }, [id]);

  const item = r?.itens[i];
  const respondida = !!item?.resposta;

  const responder = useCallback(async () => {
    if (!r || !item || !escolhida || enviando || respondida) return;
    setEnviando(true);
    try {
      const out = await api.responderReforco(r.id, item.ordem, escolhida);
      setR({
        ...r,
        ...out.reforco,
        itens: r.itens.map((it) =>
          it.ordem === item.ordem
            ? {
                ...it,
                resposta: escolhida,
                acertou: out.acertou,
                questao: { ...it.questao, gabarito: out.gabarito, explicacao: out.explicacao },
              }
            : it,
        ),
      });
    } catch (e) {
      setErro(String((e as Error).message ?? e));
    } finally {
      setEnviando(false);
    }
  }, [r, item, escolhida, enviando, respondida]);

  const proxima = useCallback(() => {
    setEscolhida(null);
    setI((n) => n + 1);
    window.scrollTo({ top: 0 });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || !item) return;
      const k = e.key.toUpperCase();
      if (!respondida && item.questao.alternativas.some((a) => a.letra === k)) {
        e.preventDefault();
        setEscolhida(k);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (respondida) proxima();
        else void responder();
      }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [item, respondida, responder, proxima]);

  if (erro) {
    return (
      <div className="px-[clamp(24px,4vw,56px)] py-[34px]">
        <Erro>{erro}</Erro>
      </div>
    );
  }
  if (!r) {
    return <div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">carregando…</div>;
  }

  const certas = r.itens.filter((it) => it.acertou).length;

  if (r.estado === "aguardando_questoes") {
    return (
      <div className="max-w-[720px] px-[clamp(24px,4vw,56px)] py-[44px]">
        <h1 className="m-0 mb-3 text-[28px]">{r.assunto}</h1>
        <p className="m-0 mb-6 text-[15px] text-muted">
          As 5 questões deste reforço ainda não foram escritas. Volte ao simulado e clique em “Gerar reforço” neste assunto.
        </p>
        <Link href="/simulado" className="btn btn-secondary">Voltar ao simulado</Link>
      </div>
    );
  }

  if (!item) {
    const passou = r.estado === "aprovado";
    return (
      <div className="max-w-[720px] px-[clamp(24px,4vw,56px)] py-[44px]">
        <div className="text-[12px] uppercase tracking-[0.08em] text-accent">{r.materia_nome}</div>
        <h1 className="m-0 mb-3 mt-1 text-[clamp(28px,3.4vw,38px)] leading-[1.08] tracking-[-0.02em]">
          {passou ? "Reforço aprovado" : "Ainda não"}
        </h1>
        <p className="tnum m-0 mb-6 max-w-[52ch] text-[15px] text-muted">
          {r.assunto}: {certas} de {r.itens.length}.{" "}
          {passou
            ? "Passou dos 75%. Quando todos os assuntos passarem, o próximo simulado abre, e este assunto volta nele."
            : `Precisava de ${r.minimo}. Abriu a rodada ${r.rodada + 1}: volte ao simulado e clique em “Gerar reforço” — as 5 novas miram no que você errou agora.`}
        </p>
        <Link href="/simulado" className="btn btn-primary px-[18px] py-[10px]">
          Voltar ao simulado
          <Icone nome="seta" />
        </Link>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center gap-[18px] px-[clamp(24px,4vw,56px)] pt-5">
        <div className="flex min-w-0 items-baseline gap-2 text-[12px] uppercase tracking-[0.06em]">
          <span className="text-accent">Reforço</span>
          <span className="text-neutral-700">/</span>
          <span className="truncate text-neutral-500">{r.assunto}</span>
          {r.rodada > 1 && <span className="flex-none text-neutral-500">· rodada {r.rodada}</span>}
        </div>
        <span className="tnum ml-auto flex-none text-[12px] text-neutral-500">
          {i + 1} / {r.itens.length} · {certas} {certas === 1 ? "certa" : "certas"} · precisa de {r.minimo}
        </span>
      </header>
      <div className="mt-[18px] h-[2px] bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
        <div className="h-[2px] bg-accent transition-[width] duration-300" style={{ width: `${((i + (respondida ? 1 : 0)) / r.itens.length) * 100}%` }} />
      </div>

      <div className="flex-1 px-[clamp(24px,4vw,56px)] pb-16 pt-10">
        <div className="max-w-[720px]">
          <CorpoQuestao q={item.questao} />
          {respondida ? (
            <Corrigida q={item.questao} resposta={item.resposta} />
          ) : (
            <div className="flex flex-col gap-2">
              {item.questao.alternativas.map((a) => (
                <Opcao
                  key={a.letra}
                  letra={a.letra}
                  texto={a.texto}
                  marca={escolhida === a.letra ? "marcada" : "neutra"}
                  onClick={() => setEscolhida(a.letra)}
                />
              ))}
            </div>
          )}
          {respondida && <PorQue q={item.questao} />}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            {respondida ? (
              <>
                <span className="text-[15px] font-medium">{item.acertou ? "Certo." : "Errado — o gabarito está marcado."}</span>
                <button type="button" onClick={proxima} className="btn btn-primary ml-auto px-[18px] py-[10px]">
                  {i + 1 >= r.itens.length ? "Ver o resultado" : "Próxima"}
                  <Icone nome="seta" tamanho={15} />
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => void responder()}
                  disabled={!escolhida || enviando}
                  className="btn btn-primary px-[18px] py-[10px] text-[15px]"
                >
                  {enviando ? "…" : "Responder"}
                </button>
                <span className="text-[12px] text-neutral-600">
                  {escolhida ? `Alternativa ${escolhida} · Enter responde` : "Escolha uma alternativa"}
                </span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">carregando…</div>}>
      <Reforco />
    </Suspense>
  );
}
