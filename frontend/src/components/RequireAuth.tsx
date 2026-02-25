import { Navigate, useLocation } from "react-router-dom";
import type { JSX } from "react";
import { useAuth } from "../auth";

export default function RequireAuth({ children }: { children: JSX.Element }) {
  const { tokens } = useAuth();
  const location = useLocation();
  if (!tokens?.accessToken) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return children;
}
