"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Icone } from "@/components/icones";
import { api } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const entrar = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      await api.entrar(email, senha);
      router.replace("/");
    } catch (err) {
      setErro(String((err as Error).message ?? err));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center px-6">
      <form
        onSubmit={entrar}
        className="card elev-md w-[min(360px,100%)] px-7 py-8"
      >
        <div className="mb-6 flex items-center gap-[9px]">
          <Icone nome="logo" tamanho={18} className="text-accent" />
          <h1 className="m-0 text-[22px]">Copiloto</h1>
        </div>

        <label className="card-kicker mb-[6px] block text-neutral-400" htmlFor="email">
          E-mail
        </label>
        <input
          id="email"
          type="email"
          className="input mb-4"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
          required
        />

        <label className="card-kicker mb-[6px] block text-neutral-400" htmlFor="senha">
          Senha
        </label>
        <input
          id="senha"
          type="password"
          className="input mb-5"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          autoComplete="current-password"
          required
        />

        {erro && <p className="m-0 mb-3 text-[13px] text-accent-300">{erro}</p>}

        <button
          type="submit"
          disabled={enviando}
          className="btn btn-primary w-full py-[9px]"
        >
          {enviando ? "entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
