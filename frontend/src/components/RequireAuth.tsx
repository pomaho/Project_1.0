import { Navigate } from "react-router-dom";
import type { JSX } from "react";
import { useAuth } from "../auth";

export default function RequireAuth({ children }: { children: JSX.Element }) {
  const { tokens } = useAuth();
  if (!tokens?.accessToken) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
