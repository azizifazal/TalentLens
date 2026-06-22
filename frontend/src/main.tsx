import React from "react";
import ReactDOM from "react-dom/client";
import App from "@/App";
import { configureAuth } from "@/api/auth-config";
import "@/index.css";

configureAuth();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
