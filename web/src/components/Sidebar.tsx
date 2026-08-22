"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api, MUTOU } from "@/lib/api";
import type { ModuloResumo, Resumo, Usuario } from "@/lib/tipos";

import { Icone, type NomeIcone } from "./icones";

type Item = { href: string; rotulo: string; icone: NomeIcone };

const ESTUDO: Item[] = [
  { href: "/", rotulo: "Hoje", icone: "hoje" },
  { href: "/revisar", rotulo: "Revisar", icone: "revisar" },
  { href: "/modulos", rotulo: "Módulos", icone: "modulos" },
  { href: "/formatos", rotulo: "Formatos de questão", icone: "formatos" },
];

const RESTO: Item[] = [
  { href: "/conhecimento", rotulo: "Conhecimento", icone: "conhecimento" },
  { href: "/transcrever", rotulo: "Transcrever", icone: "transcrever" },
  { href: "/fila", rotulo: "Fila", icone: "fila" },
  { href: "/candidaturas", rotulo: "Candidaturas", icone: "candidaturas" },
];

function Link_({
  item,
  ativo,
  contador,
  destaque,
}: {
  item: Item;
  ativo: boolean;
  contador?: number;
  destaque?: boolean;
}) {
  return (
    <Link
      href={item.href}
      aria-current={ativo ? "page" : undefined}
      className={`flex items-center gap-[10px] rounded-[8px] px-[10px] py-[7px] text-[14px] no-underline transition-colors ${
        ativo
          ? "bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)] text-accent"
          : "text-[color-mix(in_srgb,var(--color-text)_78%,transparent)] hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)] hover:text-text"
      }`}
    >
      <Icone nome={item.icone} />
      {item.rotulo}
      {contador ? (
        <span
          className={`tnum ml-auto text-[11px] ${destaque ? "text-accent" : "text-neutral-400"}`}
        >
          {contador}
        </span>
      ) : null}
    </Link>
  );
}

export function Sidebar() {
  const rota = usePathname();
  const router = useRouter();
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [modulos, setModulos] = useState<ModuloResumo[]>([]);
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [pendentes, setPendentes] = useState(0);

  const carregar = useCallback(() => {
    api.resumo().then(setResumo).catch(() => {});
    api.modulos().then(setModulos).catch(() => {});
    api.eu().then(setUsuario).catch(() => {});
    api
      .filaAprovacao()
      .then((f) => setPendentes(Number(f.total ?? 0)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    carregar();
  }, [rota, carregar]);

  // Escrita em qualquer tela mexe nos contadores daqui.
  useEffect(() => {
    const onMutou = () => carregar();
    addEventListener(MUTOU, onMutou);
    return () => removeEventListener(MUTOU, onMutou);
  }, [carregar]);

  const trilhas = ["concurso", "especializacao"] as const;
  const rotulo: Record<string, string> = {
    concurso: "Concurso",
    especializacao: "Especialização",
  };

  return (
    <aside className="flex w-[238px] flex-none flex-col gap-[26px] border-r border-divider py-[22px] pb-6">
      <Link
        href="/"
        className="flex items-center gap-[9px] px-5 text-text no-underline"
      >
        <Icone nome="logo" tamanho={17} className="text-accent" />
        <span className="font-heading text-[17px] font-medium tracking-[-0.01em]">
          Copiloto
        </span>
      </Link>

      <nav className="flex flex-col gap-px px-[10px]">
        {ESTUDO.map((i) => (
          <Link_
            key={i.href}
            item={i}
            ativo={rota === i.href}
            contador={i.href === "/revisar" ? resumo?.hoje : undefined}
            destaque
          />
        ))}
        <div className="mx-[10px] my-[10px] h-px bg-divider" />
        {RESTO.map((i) => (
          <Link_
            key={i.href}
            item={i}
            ativo={rota.startsWith(i.href)}
            contador={i.href === "/fila" ? pendentes : undefined}
          />
        ))}
      </nav>

      {modulos.length > 0 && (
        <div className="flex flex-col gap-[14px] px-5">
          {trilhas.map((t) => {
            const doGrupo = modulos.filter((m) => m.trilha === t);
            if (!doGrupo.length) return null;
            return (
              <div key={t} className="flex flex-col gap-[7px]">
                <div className="text-[10px] uppercase tracking-[0.1em] text-neutral-500">
                  {rotulo[t]}
                </div>
                {doGrupo.map((m) => (
                  <Link
                    key={m.id}
                    href={`/modulos#${m.id}`}
                    className="flex justify-between text-[13px] text-[color-mix(in_srgb,var(--color-text)_72%,transparent)] no-underline hover:text-accent"
                  >
                    {m.nome}
                    <span className="tnum text-neutral-600">{m.questoes}</span>
                  </Link>
                ))}
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-auto flex flex-col gap-[9px] px-5">
        <div className="tnum text-[11px] text-neutral-600">
          {resumo
            ? `${resumo.total} no banco · ${resumo.respondidas_hoje} respondidas hoje`
            : "carregando…"}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={carregar}
            className="btn btn-secondary px-[10px] py-[5px] text-[12px]"
          >
            ↻ atualizar
          </button>
          <button
            type="button"
            className="btn btn-ghost text-[12px]"
            onClick={async () => {
              await api.sair().catch(() => {});
              router.push("/login");
            }}
          >
            sair
          </button>
        </div>
        <div className="tnum text-[10.5px] text-neutral-700">
          {usuario ? usuario.email : "não autenticado"}
        </div>
      </div>
    </aside>
  );
}
