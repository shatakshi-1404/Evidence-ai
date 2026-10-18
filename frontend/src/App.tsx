import { Link, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ProtectedRoute, PublicOnlyRoute } from "./components/RouteGuards";
import AskPage from "./pages/AskPage";
import EvaluationPage from "./pages/EvaluationPage";
import HistoryPage from "./pages/HistoryPage";
import LibraryPage from "./pages/LibraryPage";
import LoginPage from "./pages/LoginPage";
import ReaderPage from "./pages/ReaderPage";
import RegisterPage from "./pages/RegisterPage";
import SearchPage from "./pages/SearchPage";

function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center">
      <h1 className="font-serif text-3xl font-semibold">Page not found</h1>
      <p className="text-sm text-navy-soft">That address doesn't exist.</p>
      <Link to="/" className="mt-2 text-sm font-medium text-teal hover:underline">
        Go home
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/library" replace />} />
          <Route path="library/:collectionId?" element={<LibraryPage />} />
          <Route path="documents/:documentId" element={<ReaderPage />} />
          <Route path="ask" element={<AskPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="evaluation" element={<EvaluationPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
