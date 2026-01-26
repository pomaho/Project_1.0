import { Route, Routes, Navigate } from "react-router-dom";
import LoginPage from "./pages/Login";
import GalleryPage from "./pages/Gallery";
import RequireAuth from "./components/RequireAuth";
import AdminPage from "./pages/Admin";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <GalleryPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAuth>
            <AdminPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
