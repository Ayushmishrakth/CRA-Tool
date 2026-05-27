import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./ProtectedRoute";
import MainLayout from "../layouts/MainLayout";
import AssessmentDetailPage from "../pages/AssessmentDetailPage";
import AssessmentsPage from "../pages/AssessmentsPage";
import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";

export default function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/assessments" element={<AssessmentsPage />} />
          <Route path="/assessments/:assessmentId" element={<AssessmentDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
