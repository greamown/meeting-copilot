import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n";
import "./styles.css";
import "./extras.css";
import "./projects.css";
import "./knowledge.css";
import "./languages.css";
import "./auth.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 5_000 } } });
createRoot(document.getElementById("root")!).render(<StrictMode><ErrorBoundary><QueryClientProvider client={queryClient}><I18nProvider><BrowserRouter><App/></BrowserRouter></I18nProvider></QueryClientProvider></ErrorBoundary></StrictMode>);
