/**
 * MSAL configuration — multi-tenant CRA SaaS (SPA).
 * Values align with Azure App Registration (Entra ID).
 */

export const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_MSAL_CLIENT_ID,

    authority: "https://login.microsoftonline.com/common",

    redirectUri: "http://localhost:3000",

    postLogoutRedirectUri: "http://localhost:3000",

    navigateToLoginRequestUrl: false,
  },

  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

export const loginRequest = {
  scopes: ["openid", "profile", "email", "User.Read"],
};

/** Used by silent / popup token acquisition after login. */
export const tokenRequest = {
  scopes: loginRequest.scopes,
};

/** Used by logout popup. */
export const logoutRequest = {
  postLogoutRedirectUri: "http://localhost:3000",
  mainWindowRedirectUri: "http://localhost:3000",
};
