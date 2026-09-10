import React from "react";
import { createRoot } from "react-dom/client";
import { WorkspaceProvider } from "./context/WorkspaceContext";
import { Workspace } from "./components/Workspace";
import { ErrorBoundary } from "./ErrorBoundary";
import "./styles.css";

function App() {
  return (
    <ErrorBoundary>
      <WorkspaceProvider>
        <Workspace />
      </WorkspaceProvider>
    </ErrorBoundary>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
