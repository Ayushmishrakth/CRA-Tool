import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { tokenStorage } from "../utils/tokenStorage";
import LoadingSpinner from "../components/LoadingSpinner";

/**
 * Protects CRA routes — requires CRA JWT (from backend), not only MSAL session.
 */
export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading, refreshUser, user } = useAuth();
  const location = useLocation();
  const [hydrating, setHydrating] = useState(false);

  const hasCraToken = tokenStorage.hasAccessToken();

  useEffect(() => {
    if (hasCraToken && !user && !loading) {
      setHydrating(true);
      refreshUser().finally(() => setHydrating(false));
    }
  }, [hasCraToken, user, loading, refreshUser]);

  if (loading || hydrating) {
    return <LoadingSpinner label="Checking session..." />;
  }

  if (!hasCraToken || !isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
