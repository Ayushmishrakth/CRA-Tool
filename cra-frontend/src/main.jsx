import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import {
  createMsalInstance,
  registerMsalEventCallbacks,
} from "./auth/msalInstance";
import "./index.css";

async function bootstrap() {
  const msalInstance = createMsalInstance();
  await msalInstance.initialize();
  registerMsalEventCallbacks(msalInstance);

  const redirectResult = await msalInstance.handleRedirectPromise();
  if (redirectResult?.account) {
    msalInstance.setActiveAccount(redirectResult.account);
  } else {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0]);
    }
  }

  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

bootstrap().catch((err) => {
  console.error("[CRA] Bootstrap failed:", err);
});
