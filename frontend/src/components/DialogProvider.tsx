import { AlertTriangle, X } from "lucide-react";
import {
  FormEvent,
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useI18n } from "../i18n";

type DialogOptions = {
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
};

type PromptOptions = DialogOptions & {
  initialValue?: string;
  label?: string;
};

type DialogState =
  | ({ kind: "confirm" } & DialogOptions)
  | ({ kind: "prompt" } & PromptOptions)
  | ({ kind: "alert" } & DialogOptions);

type DialogApi = {
  confirm: (options: DialogOptions) => Promise<boolean>;
  prompt: (options: PromptOptions) => Promise<string | null>;
  alert: (options: DialogOptions) => Promise<void>;
};

const DialogContext = createContext<DialogApi | null>(null);

export function DialogProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [value, setValue] = useState("");
  const resolver = useRef<(result: boolean | string | null) => void>(
    () => undefined,
  );
  const input = useRef<HTMLTextAreaElement>(null);

  const open = useCallback(
    <T extends boolean | string | null>(next: DialogState) => {
      setValue(next.kind === "prompt" ? (next.initialValue ?? "") : "");
      setDialog(next);
      return new Promise<T>((resolve) => {
        resolver.current = resolve as (result: boolean | string | null) => void;
      });
    },
    [],
  );
  const close = useCallback((result: boolean | string | null) => {
    resolver.current(result);
    setDialog(null);
  }, []);

  useEffect(() => {
    if (!dialog) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape")
        close(dialog.kind === "confirm" ? false : null);
    };
    document.addEventListener("keydown", onKeyDown);
    input.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [close, dialog]);

  const api: DialogApi = {
    confirm: (options) => open<boolean>({ kind: "confirm", ...options }),
    prompt: (options) => open<string | null>({ kind: "prompt", ...options }),
    alert: (options) =>
      open<null>({ kind: "alert", ...options }).then(() => undefined),
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (dialog?.kind === "prompt" && value.trim()) close(value.trim());
  };

  return (
    <DialogContext.Provider value={api}>
      {children}
      {dialog && (
        <div
          className="modal-backdrop app-dialog-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget)
              close(dialog.kind === "confirm" ? false : null);
          }}
        >
          <form
            className="modal app-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="app-dialog-title"
            onSubmit={submit}
          >
            <header>
              <div className="app-dialog-title">
                <span
                  className={
                    dialog.danger ? "dialog-mark danger" : "dialog-mark"
                  }
                >
                  {dialog.danger && <AlertTriangle />}
                </span>
                <div>
                  <p>
                    {dialog.danger
                      ? t("Caution").toUpperCase()
                      : "MEETING COPILOT"}
                  </p>
                  <h2 id="app-dialog-title">{dialog.title}</h2>
                </div>
              </div>
              <button
                type="button"
                className="icon-button"
                title={t("Close")}
                onClick={() => close(dialog.kind === "confirm" ? false : null)}
              >
                <X />
              </button>
            </header>
            <p className="app-dialog-message">{dialog.message}</p>
            {dialog.kind === "prompt" && (
              <label className="app-dialog-field">
                {dialog.label ?? t("Content")}
                <textarea
                  ref={input}
                  required
                  rows={5}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                />
              </label>
            )}
            <footer>
              <button
                type="button"
                className="button"
                onClick={() => close(dialog.kind === "confirm" ? false : null)}
              >
                {dialog.kind === "alert" ? t("Close") : t("Cancel")}
              </button>
              {dialog.kind !== "alert" && (
                <button
                  className={`button ${dialog.danger ? "danger" : "primary"}`}
                  type="submit"
                  onClick={
                    dialog.kind === "confirm" ? () => close(true) : undefined
                  }
                >
                  {dialog.confirmLabel ?? t("Confirm")}
                </button>
              )}
            </footer>
          </form>
        </div>
      )}
    </DialogContext.Provider>
  );
}

export function useDialogs(): DialogApi {
  const value = useContext(DialogContext);
  if (!value) throw new Error("useDialogs must be used inside DialogProvider");
  return value;
}
