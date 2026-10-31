"use client";

import { Enunciado, TextoMarcado } from "@/components/Enunciado";
import { ImagemQuestao } from "@/components/ImagemQuestao";
import type { QuestaoProva } from "@/lib/tipos";

/** "62,50" — a nota do edital tem duas casas, e é assim que ela sai no resultado. */
export function nota(n: number | null): string {
  return n === null
    ? "—"
    : n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * A questão do simulado — prova, correção e reforço desenham a mesma coisa.
 *
 * Mesma ordem da revisão, que é a ordem do caderno: comando, texto de apoio,
 * código, enunciado, figura, afirmações. A figura vem depois do enunciado
 * porque é onde ela estava na prova.
 */
export function CorpoQuestao({ q }: { q: QuestaoProva }) {
  return (
    <>
      {q.comando && (
        <p className="m-0 mb-4 text-[14px] leading-[1.55] text-muted">{q.comando}</p>
      )}
      {q.texto_base && (
        <div className="mb-4 max-h-[46vh] overflow-y-auto border-l-2 border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] pl-4">
          <Enunciado texto={q.texto_base} className="text-[15px] leading-[1.6] text-muted" />
          {q.texto_base_fonte && (
            <p className="m-0 mt-1 text-[12px] text-neutral-600">{q.texto_base_fonte}</p>
          )}
        </div>
      )}
      {q.codigo && (
        <pre className="mb-4 overflow-x-auto rounded-[8px] border border-divider bg-[color-mix(in_srgb,black_25%,transparent)] p-[14px] font-mono text-[13px] leading-[1.6]">
          {q.codigo}
        </pre>
      )}
      <Enunciado
        texto={q.enunciado}
        className="mb-4 text-[18px] leading-[1.5] tracking-[-0.005em]"
      />
      {(q.imagem || q.imagem_alt) && (
        <ImagemQuestao arquivo={q.imagem} alt={q.imagem_alt} className="mb-5 max-w-[560px]" />
      )}
      {q.afirmacoes.length > 0 && (
        <ol className="m-0 mb-4 flex list-[upper-roman] flex-col gap-[10px] pl-[30px] text-[15.5px] leading-[1.55] text-[color-mix(in_srgb,var(--color-text)_88%,transparent)]">
          {q.afirmacoes.map((a, n) => (
            <li key={n}>{a}</li>
          ))}
        </ol>
      )}
    </>
  );
}

type Marca = "marcada" | "certa" | "errada" | "neutra";

/**
 * Uma alternativa. Na prova só existe "marcada"; na correção, "certa" é o
 * gabarito e "errada" é o que eu marquei quando não era o gabarito.
 */
export function Opcao({
  letra,
  texto,
  marca,
  travada,
  onClick,
}: {
  letra: string;
  texto: string;
  marca: Marca;
  travada?: boolean;
  onClick?: () => void;
}) {
  const estilo = {
    marcada:
      "border-[color-mix(in_srgb,var(--color-accent)_55%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_9%,transparent)]",
    certa:
      "border-[color-mix(in_srgb,var(--color-accent)_70%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)]",
    errada:
      "border-[color-mix(in_srgb,var(--color-text)_35%,transparent)] bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)]",
    neutra:
      "border-[color-mix(in_srgb,var(--color-text)_14%,transparent)] hover:border-[color-mix(in_srgb,var(--color-text)_30%,transparent)] hover:bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)]",
  }[marca];
  const rotulo = { marcada: "marcada", certa: "gabarito", errada: "sua resposta", neutra: "" }[
    marca
  ];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={travada}
      className={`flex w-full items-start gap-3 rounded-[10px] border px-[14px] py-[11px] text-left text-[15px] transition-colors ${estilo} ${travada ? "cursor-default" : ""}`}
    >
      <span
        className={`tnum mt-px w-[18px] flex-none text-[13px] font-medium ${marca === "neutra" ? "text-neutral-500" : "text-accent"}`}
      >
        {letra}
      </span>
      <span
        className={`min-w-0 flex-1 leading-[1.5] ${marca === "errada" ? "line-through decoration-[color-mix(in_srgb,var(--color-text)_40%,transparent)]" : ""}`}
      >
        <TextoMarcado texto={texto} />
      </span>
      {rotulo && (
        <span
          className={`mt-px flex-none text-[11px] ${marca === "certa" ? "text-accent" : "text-neutral-500"}`}
        >
          {rotulo}
        </span>
      )}
    </button>
  );
}

/** A explicação depois de corrigir — mesma caixa da revisão. */
export function PorQue({ q }: { q: QuestaoProva }) {
  return (
    <div className="mt-5 rounded-[10px] border border-divider bg-surface p-4">
      <div className="card-kicker mb-[6px]">Por quê</div>
      {q.explicacao ? (
        <Enunciado texto={q.explicacao} className="text-[14.5px] leading-[1.6] text-muted" />
      ) : (
        <p className="m-0 text-[14px] leading-[1.6] text-neutral-500">
          Esta questão não tem explicação: a banca publica gabarito, não justificativa.
        </p>
      )}
      {q.origem && <p className="m-0 mt-3 text-[12px] text-neutral-600">Fonte: {q.origem}</p>}
    </div>
  );
}

/** Correção de uma questão: alternativas travadas com gabarito e marcação. */
export function Corrigida({ q, resposta }: { q: QuestaoProva; resposta: string | null }) {
  return (
    <div className="flex flex-col gap-2">
      {q.alternativas.map((a) => (
        <Opcao
          key={a.letra}
          letra={a.letra}
          texto={a.texto}
          travada
          marca={
            a.letra === q.gabarito ? "certa" : a.letra === resposta ? "errada" : "neutra"
          }
        />
      ))}
    </div>
  );
}
