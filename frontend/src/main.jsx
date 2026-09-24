import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function App() {
  return <main className="min-h-screen p-8 text-slate-900">QualBot foundation</main>;
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
