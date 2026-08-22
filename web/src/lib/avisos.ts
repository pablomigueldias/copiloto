"use client";

import { useCallback, useState } from "react";

/** Um aviso por vez, com o texto e se é erro. */
export function useAvisos() {
  const [aviso, setAviso] = useState<{ texto: string; erro?: boolean } | null>(
    null,
  );
  const ok = useCallback((texto: string) => setAviso({ texto }), []);
  const falhou = useCallback(
    (texto: string, e?: unknown) =>
      setAviso({
        texto: e ? `${texto}: ${(e as Error).message ?? e}` : texto,
        erro: true,
      }),
    [],
  );
  const fechar = useCallback(() => setAviso(null), []);
  return { aviso, ok, falhou, fechar };
}
