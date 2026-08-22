"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icone } from "@/components/icones";
import {
  Barra,
  Cabecalho,
  Erro,
  Numero,
  Vazio,
  plural,
  quando,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { ModuloResumo, Resumo } from "@/lib/tipos";

export default function Hoje() {
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [modulos, setModulos] = useState<ModuloResumo[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.resumo(), api.modulos()])
      .then(([r, m]) => {
        setResumo(r);
        setModulos(m);
      })
      .catch((e) => setErro(String(e.message ?? e)));
  }, []);

  const hoje = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  const vencendo = resumo?.hoje ?? 0;
  const naoVistas = modulos?.every((m) => m.questoes === 0) ?? false;

  return (
    <div className="max-w-[1180px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>{hoje}</Cabecalho>

      <form
        action="/conhecimento"
        className="mb-[30px] flex max-w-[620px] items-stretch gap-2"
      >
        <input
          className="input min-h-[40px] flex-1 text-[15px]"
          name="q"
          placeholder="o que eu estudei sobre…?"
          autoComplete="off"
        />
        <button type="submit" className="btn btn-secondary px-4 py-[9px]">
          perguntar
        </button>
      </form>

      {erro && <Erro>{erro}</Erro>}

      <section className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <h1 className="tnum m-0 mb-3 text-[clamp(38px,4.6vw,56px)] leading-[1.04] tracking-[-0.02em]">
            {vencendo === 0 ? (
              <>
                Nada volta
                <br />
                hoje
              </>
            ) : (
              <>
                {vencendo} {vencendo === 1 ? "questão" : "questões"}
                <br />
                {vencendo === 1 ? "volta" : "voltam"} hoje
              </>
            )}
          </h1>
          <p className="m-0 max-w-[46ch] text-[15px] text-muted">
            {vencendo === 0
              ? "A fila está limpa. Cadastre questão nova ou espere — o que você acertou hoje volta daqui a sete dias."
              : `As que você errou entram primeiro — elas voltam a cada dois dias até saírem certas.`}
          </p>
        </div>
        <div className="flex flex-none gap-2">
          <Link
            href="/revisar"
            className="btn btn-primary px-[18px] py-[10px] text-[15px]"
            aria-disabled={vencendo === 0}
          >
            Começar revisão
            <Icone nome="seta" />
          </Link>
          <Link href="/modulos" className="btn btn-secondary px-4 py-[10px]">
            Escolher módulo
          </Link>
        </div>
      </section>

      <div className="my-[30px] flex flex-wrap gap-[38px]">
        <Numero valor={resumo?.novas ?? 0} rotulo="Nunca respondidas" />
        <Numero
          valor={resumo?.de_erro ?? 0}
          rotulo="Voltando de erro"
          cor="text-accent-300"
        />
        <Numero
          valor={resumo?.adiadas ?? 0}
          rotulo="Adiadas por facilidade"
          cor="text-neutral-400"
        />
        <Numero valor={resumo?.dominadas ?? 0} rotulo="Dominadas" />
        <Numero valor={resumo?.total ?? 0} rotulo="Questões no banco" />
      </div>

      <hr className="hr mb-[30px]" />

      <div className="grid items-start gap-[clamp(28px,4vw,64px)] lg:grid-cols-[minmax(0,7fr)_minmax(260px,3fr)]">
        <section>
          <div className="mb-4 flex items-baseline justify-between gap-4">
            <h2 className="m-0 text-[20px]">Progresso por módulo</h2>
            <div className="flex flex-wrap justify-end gap-x-[14px] gap-y-2 text-[11px] text-neutral-500">
              <span className="inline-flex items-center gap-[6px] whitespace-nowrap">
                <span className="h-[3px] w-[14px] rounded-sm bg-accent" />
                dominadas
              </span>
              <span className="inline-flex items-center gap-[6px] whitespace-nowrap">
                <span className="h-[3px] w-[14px] rounded-sm bg-accent-800" />
                com erro
              </span>
            </div>
          </div>

          {naoVistas || modulos?.length === 0 ? (
            <Vazio
              titulo="Nenhum módulo ainda"
              acao={{ href: "/modulos", rotulo: "Ver módulos" }}
            >
              Importe um acervo com{" "}
              <code className="font-mono text-[13px] text-accent-300">
                python scripts/importar_questoes.py
              </code>{" "}
              ou cadastre uma questão pela tela de formatos.
            </Vazio>
          ) : (
            <div className="flex flex-col gap-[18px]">
              {modulos?.map((m) => (
                <article key={m.id} className="flex flex-col gap-[9px]">
                  <div className="flex items-baseline justify-between gap-3">
                    <Link
                      href={`/modulos#${m.id}`}
                      className="text-[15px] text-text no-underline hover:text-accent"
                    >
                      {m.nome}
                    </Link>
                    <span className="tnum text-[12px] text-neutral-500">
                      {m.hoje > 0 ? (
                        <span className="text-accent">{m.hoje} hoje</span>
                      ) : (
                        quando(m.proxima_em)
                      )}
                    </span>
                  </div>
                  <Barra
                    dominadas={m.dominadas}
                    comErro={m.com_erro}
                    total={m.questoes}
                  />
                  <div className="tnum text-[12px] text-neutral-500">
                    {plural(m.questoes, "questão", "questões")} ·{" "}
                    {plural(m.topicos.length, "tópico", "tópicos")} ·{" "}
                    {m.dominadas} dominadas · {m.com_erro} com erro
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="mb-4 mt-0 text-[20px]">Como o agendamento funciona</h2>
          <div className="flex flex-col gap-[10px] text-[13.5px] text-muted">
            <p className="m-0">
              <strong className="font-medium text-text">Acertou</strong> — volta
              em 7 dias, e o intervalo cresce a cada acerto seguido, até 180.
            </p>
            <p className="m-0">
              <strong className="font-medium text-text">Errou</strong> — volta em
              2 dias e a sequência <em>zera</em>. Não recua um degrau: quem errou
              depois de 35 dias não sabia há 35 dias.
            </p>
            <p className="m-0">
              <strong className="font-medium text-text">Adiou</strong> — sai da
              fila por 30 dias, e não conta como acerto. &ldquo;Está fácil&rdquo;
              não é a mesma coisa que &ldquo;respondi certo&rdquo;.
            </p>
            <p className="m-0 mt-1 text-[12.5px] text-neutral-600">
              Toda resposta vira uma linha com data e acerto. É desse histórico
              que sai a próxima data — não de uma nota que eu me dou.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
