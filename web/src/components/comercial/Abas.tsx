"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// As seções do CRM, na ordem do CRM do prospector, mais a base de prospecção,
// de onde as clínicas vêm. O negócio é o lead: a página completa dele
// (`/comercial/leads/[id]`, Pesquisador e Redator) acende a aba Negócios.
const ABAS = [
  { href: "/comercial", rotulo: "Visão geral", exata: true },
  { href: "/comercial/empresas", rotulo: "Empresas" },
  { href: "/comercial/contatos", rotulo: "Contatos" },
  {
    href: "/comercial/negocios",
    rotulo: "Negócios",
    tambem: "/comercial/leads",
  },
  { href: "/comercial/atividades", rotulo: "Atividades" },
  { href: "/comercial/base", rotulo: "Base de prospecção" },
];

export function AbasComercial() {
  const rota = usePathname();
  return (
    <nav
      className="mb-6 flex w-fit max-w-full gap-1 overflow-x-auto rounded-[8px] border border-divider p-[3px]"
      aria-label="CRM comercial"
    >
      {ABAS.map((a) => {
        const ativa = a.exata
          ? rota === a.href
          : rota.startsWith(a.href) ||
            (!!a.tambem && rota.startsWith(a.tambem));
        return (
          <Link
            key={a.href}
            href={a.href}
            aria-current={ativa ? "page" : undefined}
            className={`whitespace-nowrap rounded-[6px] px-3 py-[5px] text-[13px] no-underline ${
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
