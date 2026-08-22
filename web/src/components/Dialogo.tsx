"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Confirmar e perguntar, sem `confirm()`/`prompt()` do navegador.
 *
 * Os nativos travam a aba inteira enquanto estão abertos — o polling da tela
 * para, o refresco para, e numa aba de automação eles congelam tudo. E a caixa
 * de uma linha do `prompt()` é pequena demais para o motivo de uma rejeição,
 * que é justamente o texto que vira sinal de treino.
 */
export function Dialogo({
  titulo,
  descricao,
  confirmar = "confirmar",
  perigo = false,
  multilinha = false,
  placeholder,
  desabilitado = false,
  children,
  onConfirmar,
  onCancelar,
}: {
  titulo: string;
  descricao?: string;
  confirmar?: string;
  perigo?: boolean;
  /** Com texto, o diálogo pergunta; sem, apenas confirma. */
  multilinha?: boolean;
  placeholder?: string;
  desabilitado?: boolean;
  /** Campos próprios — quem monta controla o estado deles. */
  children?: React.ReactNode;
  onConfirmar: (texto: string) => void;
  onCancelar: () => void;
}) {
  const [texto, setTexto] = useState("");
  const primeiro = useRef<HTMLTextAreaElement | HTMLButtonElement>(null);

  // Foco **uma vez**, na montagem, e em efeito próprio. Junto com o listener de
  // teclado ele herdava as dependências dele — que mudam a cada tecla, porque
  // quem monta passa `onConfirmar` novo a cada render. O efeito rodava a cada
  // letra e devolvia o foco ao botão de confirmar no meio da digitação: o nome
  // saía truncado e uma tecla acabava acionando o botão. Um módulo chamado "Eí"
  // foi criado assim.
  useEffect(() => {
    primeiro.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancelar();
      // Ctrl/⌘+Enter confirma de dentro do textarea, onde Enter é quebra de linha.
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !desabilitado)
        onConfirmar(texto);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [texto, desabilitado, onCancelar, onConfirmar]);

  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center bg-[rgb(0_0_0/60%)] px-6"
      onClick={onCancelar}
      role="presentation"
    >
      <div
        className="card elev-lg w-[min(460px,100%)]"
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="m-0 mb-2 text-[17px]">{titulo}</h3>
        {descricao && (
          <p className="m-0 mb-3 text-[13.5px] leading-[1.55] text-muted">
            {descricao}
          </p>
        )}
        {children}
        {multilinha && (
          <textarea
            ref={primeiro as React.RefObject<HTMLTextAreaElement>}
            className="input mb-3 min-h-[96px] resize-y"
            value={texto}
            placeholder={placeholder}
            onChange={(e) => setTexto(e.target.value)}
          />
        )}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={onCancelar}>
            cancelar
          </button>
          <button
            type="button"
            ref={
              !multilinha && !children
                ? (primeiro as React.RefObject<HTMLButtonElement>)
                : undefined
            }
            disabled={desabilitado}
            className={`btn ${perigo ? "btn-secondary" : "btn-primary"}`}
            style={
              perigo
                ? {
                    color: "var(--color-accent-200)",
                    borderColor:
                      "color-mix(in srgb, var(--color-accent) 55%, transparent)",
                  }
                : undefined
            }
            onClick={() => onConfirmar(texto)}
          >
            {confirmar}
          </button>
        </div>
      </div>
    </div>
  );
}

/** O aviso de canto: some sozinho, e não empurra a tela. */
export function Aviso({
  texto,
  erro,
  onFechar,
}: {
  texto: string;
  erro?: boolean;
  onFechar: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onFechar, erro ? 8000 : 4000);
    return () => clearTimeout(t);
  }, [texto, erro, onFechar]);

  return (
    <div
      role="status"
      className={`elev-lg fixed bottom-5 right-5 z-[70] max-w-[380px] rounded-[10px] border px-4 py-3 text-[13.5px] ${
        erro
          ? "border-[color-mix(in_srgb,var(--color-accent)_50%,transparent)] bg-surface text-accent-200"
          : "border-divider bg-surface text-text"
      }`}
    >
      {texto}
      <button
        type="button"
        onClick={onFechar}
        aria-label="fechar aviso"
        className="ml-3 text-neutral-500 hover:text-text"
      >
        ✕
      </button>
    </div>
  );
}
