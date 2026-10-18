import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { FullPageSpinner } from "./ui/spinner";

type FromState = { from?: { pathname: string; search?: string } } | null;

/** Signed-out visitors are sent to /login and returned here afterwards. */
export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <FullPageSpinner />;
  if (status === "anon") return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

/** Login and register pages: signed-in users are sent on to where they were headed. */
export function PublicOnlyRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <FullPageSpinner />;
  if (status === "authed") {
    const from = (location.state as FromState)?.from;
    return <Navigate to={from ? `${from.pathname}${from.search ?? ""}` : "/"} replace />;
  }
  return <Outlet />;
}
