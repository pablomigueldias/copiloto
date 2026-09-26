"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// As telas do CRM comercial. Cresce com a Fase 1: Hoje (passo 5) e Negócios
// (passo 7) entram aqui.
const ABAS = [
  { href: "/comercial/empresas", rotulo: "Empresas" },
  { href: "/comercial/leads", rotulo: "Leads" },
];

export function AbasComercial() {
  const rota = usePathname();
  return (
    <nav
      className="mb-6 flex w-fit gap-1 rounded-[8px] border border-divider p-[3px]"
      aria-label="CRM comercial"
    >
      {ABAS.map((a) => {
        const ativa = rota.startsWith(a.href);
        return (
          <Link
            key={a.href}
            href={a.href}
            aria-current={ativa ? "page" : undefined}
            className={`rounded-[6px] px-3 py-[5px] text-[13px] no-underline ${
              ativa
                ? "bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent"
                : "text-muted hover:text-text"
            }`}
          >
            {a.rotulo}
          </Link>
        );
      })}
    </nav>
  );
}
