"use client";

import Link from "next/link";

/** Peças que três telas ou mais repetem. Menos que isso fica na própria tela. */

export function Cabecalho({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-[26px] flex items-baseline gap-3">
      <span className="tnum text-[12px] uppercase tracking-[0.08em] text-accent">
        {children}
      </span>
      <span className="h-px flex-1 bg-gradient-to-r from-[var(--color-divider)] to-transparent" />
    </div>
  );
}

export function Numero({
  valor,
  rotulo,
  cor,
}: {
  valor: number | string;
  rotulo: string;
  cor?: string;
}) {
  return (
    <div>
      <div
        className={`tnum font-heading text-[26px] font-medium leading-none ${cor ?? ""}`}
      >
        {valor}
      </div>
      <div className="mt-[7px] text-[11px] uppercase tracking-[0.08em] text-neutral-500">
        {rotulo}
      </div>
    </div>
  );
}

/** Uma barra de três faixas: dominadas, em aprendizado, o que ainda não vi. */
export function Barra({
  dominadas,
  comErro,
  total,
}: {
  dominadas: number;
  comErro: number;
  total: number;
}) {
  const t = Math.max(total, 1);
  const pct = (n: number) => `${(n / t) * 100}%`;
  return (
    <div className="flex h-[3px] gap-px overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
      <span className="bg-accent" style={{ width: pct(dominadas) }} />
      <span className="bg-accent-800" style={{ width: pct(comErro) }} />
    </div>
  );
}

/** "1 tópico", "12 tópicos" — a tela é feita de contadores que passam por 1. */
export function plural(n: number, singular: string, plural_: string): string {
  return `${n} ${n === 1 ? singular : plural_}`;
}

export function Vazio({
  titulo,
  children,
  acao,
}: {
  titulo: string;
  children?: React.ReactNode;
  acao?: { href: string; rotulo: string };
}) {
  return (
    <div className="card flex flex-col items-start gap-3 border border-dashed border-divider">
      <h4 className="m-0 text-[16px]">{titulo}</h4>
      {children ? (
        <p className="m-0 max-w-[52ch] text-[14px] text-muted">{children}</p>
      ) : null}
      {acao ? (
        <Link href={acao.href} className="btn btn-secondary">
          {acao.rotulo}
        </Link>
      ) : null}
    </div>
  );
}

export function Erro({ children }: { children: React.ReactNode }) {
  return (
    <div className="card border-[color-mix(in_srgb,var(--color-accent)_35%,transparent)] text-[14px]">
      <div className="card-kicker mb-1 text-accent-300">não deu</div>
      {children}
    </div>
  );
}

/** "hoje", "em 3 d", "em 2 sem" — a distância, que é o que interessa na fila. */
export function quando(iso: string | null | undefined): string {
  if (!iso) return "—";
  const alvo = new Date(`${iso}T00:00:00`);
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const dias = Math.round((alvo.getTime() - hoje.getTime()) / 86_400_000);
  if (dias <= 0) return "hoje";
  if (dias === 1) return "amanhã";
  if (dias < 14) return `em ${dias} d`;
  if (dias < 60) return `em ${Math.round(dias / 7)} sem`;
  return `em ${Math.round(dias / 30)} m`;
}

export function dataLonga(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "long",
  }).format(new Date(`${iso}T00:00:00`));
}
