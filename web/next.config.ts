import type { NextConfig } from "next";

/**
 * O front fala com o FastAPI pela **mesma origem**.
 *
 * `next dev` sobe na 3000 e o backend na 8010. Sem esta reescrita, o browser
 * trataria `/api` como origem cruzada — e a autenticação do Copiloto é cookie
 * de sessão httpOnly. Cookie cross-origin custa SameSite=None, que custa HTTPS,
 * que custa certificado numa máquina local. Reescrever é uma linha.
 *
 * **8010, e não uma porta qualquer.** É a que `scripts/copiloto.sh` sobe, e o
 * backend precisa ser *o mesmo processo* do painel antigo: o estado da gravação
 * mora em memória (`_sessao` global em `app/conhecimento/gravacao.py`), não no
 * banco. Com dois uvicorn, uma transcrição iniciada num é invisível no outro —
 * foi exatamente o que aconteceu em 22/08/2026, com o Next apontando para um
 * segundo processo na 8000.
 *
 * `API_URL` sobrescreve quando a porta estiver ocupada.
 */
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8010";

const nextConfig: NextConfig = {
  // Os testes de navegador sobem um `next dev` próprio, e o Next 16 recusa um
  // segundo servidor sobre o mesmo `.next`. Trocar o diretório de build isola
  // a suíte do servidor que eu deixo aberto enquanto trabalho.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",

  // O `next dev` responde 403 aos próprios assets quando o Host não está aqui,
  // e o sintoma engana: a página abre, o JS não carrega, e o formulário volta a
  // submeter nativamente — a URL vira `/login?` e nada acontece. A suíte de
  // navegador acessa por `127.0.0.1`, que não é o mesmo host que `localhost`.
  allowedDevOrigins: ["127.0.0.1", "localhost"],

  // O projeto já tem CLAUDE.md na raiz; um segundo gerado aqui só duplica.
  agentRules: false,

  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
