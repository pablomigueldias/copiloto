"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, ApiErro } from "@/lib/api";

import { Sidebar } from "./Sidebar";

/**
 * O casco: sidebar + conteúdo, e o portão de autenticação.
 *
 * A verificação acontece **aqui**, uma vez, e não em cada página. Sem isso,
 * cada tela teria que decidir sozinha o que fazer com um 401 — e a primeira
 * que esquecesse mostraria uma tela vazia sem dizer por quê.
 */
export function Shell({ children }: { children: React.ReactNode }) {
  const rota = usePathname();
  const router = useRouter();
  const [sessao, setSessao] = useState<"checando" | "dentro" | "fora">(
    "checando",
  );

  const ehLogin = rota === "/login";

  // `data-pronto` marca a hidratação. Existe para a suíte de navegador: até o
  // React assumir os campos controlados, preencher um input escreve no DOM e o
  // primeiro render apaga — o teste digitava a senha e a tela continuava vazia,
  // sem erro nenhum para explicar. `networkidle` não cobre isso, porque a rede
  // termina antes da hidratação.
  useEffect(() => {
    document.documentElement.dataset.pronto = "1";
  }, []);
  // Derivado, não guardado: `/login` não precisa de sessão, e escrever isso
  // com um setState dentro do efeito é o que dispara render em cascata.
  const estado = ehLogin ? "fora" : sessao;

  useEffect(() => {
    if (ehLogin) return;
    api
      .eu()
      .then(() => setSessao("dentro"))
      .catch((e) => {
        setSessao("fora");
        if (e instanceof ApiErro && e.status === 401) router.replace("/login");
      });
  }, [ehLogin, router]);

  if (ehLogin) return <main className="ground min-h-screen">{children}</main>;

  if (estado !== "dentro") {
    return (
      <main className="ground grid min-h-screen place-items-center">
        <p className="text-[13px] text-neutral-500">
          {estado === "checando" ? "verificando a sessão…" : "redirecionando…"}
        </p>
      </main>
    );
  }

  return (
    <div className="ground flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
