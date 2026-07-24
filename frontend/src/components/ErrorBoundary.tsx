import { Component, ErrorInfo, ReactNode } from "react";
import { useI18n } from "../i18n";

function ErrorFallback() {
  const { t } = useI18n();
  return (
    <main className="page">
      <div className="alert error">
        <strong>{t("Page could not be displayed.")}</strong>{" "}
        {t(
          "Reload the page; meetings and transcripts remain stored in the backend.",
        )}
      </div>
      <button className="button" onClick={() => location.reload()}>
        {t("Reload")}
      </button>
    </main>
  );
}

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI boundary", error.name, info.componentStack);
  }
  render() {
    return this.state.failed ? <ErrorFallback /> : this.props.children;
  }
}
