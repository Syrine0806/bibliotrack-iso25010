import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import type { Role } from "./api/types";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { homeFor, Layout, RequireAuth } from "./components/Layout";
import { Loading } from "./components/ui";
import { AuditPage, DashboardPage, UsersPage } from "./pages/AdminPages";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { BookDetailPage } from "./pages/BookDetailPage";
import { BookFormPage } from "./pages/BookFormPage";
import { CatalogPage } from "./pages/CatalogPage";
import { LoansPage, PenaltiesPage, ReservationsPage } from "./pages/CirculationPages";
import { ReferentialsPage } from "./pages/ReferentialsPage";

const STAFF: Role[] = ["ADMIN", "BIBLIOTHECAIRE"];

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/inscription" element={<RegisterPage />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/" element={<Home />} />
            <Route path="/catalogue" element={<CatalogPage />} />
            <Route path="/catalogue/nouveau" element={<RequireAuth roles={STAFF}><BookFormPage /></RequireAuth>} />
            <Route path="/catalogue/:id" element={<BookDetailPage />} />
            <Route path="/catalogue/:id/modifier" element={<RequireAuth roles={STAFF}><BookFormPage /></RequireAuth>} />
            <Route path="/emprunts" element={<LoansPage />} />
            <Route path="/reservations" element={<ReservationsPage />} />
            <Route path="/penalites" element={<PenaltiesPage />} />
            <Route path="/dashboard" element={<RequireAuth roles={STAFF}><DashboardPage /></RequireAuth>} />
            <Route path="/referentiels" element={<RequireAuth roles={STAFF}><ReferentialsPage /></RequireAuth>} />
            <Route path="/utilisateurs" element={<RequireAuth roles={STAFF}><UsersPage /></RequireAuth>} />
            <Route path="/audit" element={<RequireAuth roles={["ADMIN"]}><AuditPage /></RequireAuth>} />
          </Route>
          <Route path="*" element={<Home />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
