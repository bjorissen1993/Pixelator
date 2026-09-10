import React from "react";
import { createRoot } from "react-dom/client";
import { WorkspaceProvider } from "./context/WorkspaceContext";
import { Workspace } from "./components/Workspace";
import "./styles.css";

function App() {
  return (
    <WorkspaceProvider>
      <Workspace />
    </WorkspaceProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
