/* O único jeito de falar com o servidor.
 *
 * Centralizado por um motivo que já mordeu o repo antigo: quando existem quatro
 * caminhos de chamada, três esquecem alguma coisa. Aqui o CSRF, o `credentials`
 * e o tratamento de 401 são resolvidos uma vez.
 */

/** Quem reage à sessão expirada — o `main.js` registra o dele no início. */
let aoExpirar = () => {};

export function quandoExpirar(callback) {
  aoExpirar = callback;
}

function csrf() {
  // O cookie CSRF é legível de propósito (double-submit): o servidor exige
  // header == cookie, e só quem está na mesma origem consegue ler.
  const nome = document.cookie.includes("__Host-csrf") ? "__Host-csrf" : "csrf_token";
  const achado = document.cookie.split("; ").find((c) => c.startsWith(nome + "="));
  return achado ? decodeURIComponent(achado.split("=")[1]) : "";
}

export async function api(caminho, opcoes = {}) {
  const metodo = (opcoes.method || "GET").toUpperCase();
  const cabecalhos = { ...(opcoes.headers || {}) };
  if (metodo !== "GET") {
    cabecalhos["Content-Type"] = "application/json";
    cabecalhos["X-CSRF-Token"] = csrf();
  }

  const r = await fetch(caminho, { ...opcoes, headers: cabecalhos, credentials: "same-origin" });
  if (r.status === 401) {
    aoExpirar();
    throw new Error("sessão expirada");
  }
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}));
    throw new Error(corpo.detail || `erro ${r.status}`);
  }
  return r.status === 204 ? null : r.json();
}
