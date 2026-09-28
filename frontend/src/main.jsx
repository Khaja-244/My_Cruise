import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './index.css';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/layout/Layout';
import ProtectedRoute from './routes/ProtectedRoute';
import AdminRoute from './routes/AdminRoute';
import PartnerRoute from './routes/PartnerRoute';
import ErrorBoundary from './components/ui/ErrorBoundary';
import ToastViewport from './components/ui/ToastViewport';
import Landing from './pages/public/Landing';
import Login from './pages/public/Login';
import Register from './pages/public/Register';
import ForgotPassword from './pages/public/ForgotPassword';
import VerifyOtp from './pages/public/VerifyOtp';
import ResetPassword from './pages/public/ResetPassword';
import Cruises from './pages/public/Cruises';
import CruiseDetail from './pages/public/CruiseDetail';
import Legal from './pages/public/Legal';
import Dashboard from './pages/traveler/Dashboard';
import Bookings from './pages/traveler/Bookings';
import BookingWizard from './pages/traveler/BookingWizard';
import BookingDetail from './pages/traveler/BookingDetail';
import Notifications from './pages/traveler/Notifications';
import Saved from './pages/traveler/Saved';
import Profile from './pages/traveler/Profile';
import PartnerApplication from './pages/traveler/PartnerApplication';
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminResource from './pages/admin/AdminResource';
import AdminBookingDetail from './pages/admin/AdminBookingDetail';
import PartnerManagement from './pages/admin/PartnerManagement';
import PartnerDashboard from './pages/partner/PartnerDashboard';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function NotFound() {
  return (
    <div className="container-app py-20 text-center">
      <p className="eyebrow">404</p>
      <h1 className="section-title mt-3">This page has sailed away.</h1>
      <p className="muted mt-3">The page you requested does not exist or is no longer available.</p>
      <a href="/" className="btn btn-primary mt-7">Return home</a>
    </div>
  );
}

function AppRoutes() {
  const location = useLocation();

  return (
    <ErrorBoundary resetKey={location.pathname}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/verify-otp" element={<VerifyOtp />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/cruises" element={<Cruises />} />
          <Route path="/cruises/:slug" element={<CruiseDetail />} />
          <Route path="/terms" element={<Legal title="Terms of Service" />} />
          <Route path="/privacy" element={<Legal title="Privacy Policy" />} />
          <Route path="/refund-policy" element={<Legal title="Refund & Cancellation Policy" />} />
          <Route path="/booking-policy" element={<Legal title="Booking Policy" />} />
          <Route path="/faq" element={<Legal title="FAQ" />} />
          <Route path="/support" element={<Legal title="Contact & Support" />} />
          <Route path="/about" element={<Legal title="About my_cruise" />} />

          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/saved" element={<ProtectedRoute><Saved /></ProtectedRoute>} />
          <Route path="/bookings" element={<ProtectedRoute><Bookings /></ProtectedRoute>} />
          <Route path="/bookings/:reference" element={<ProtectedRoute><BookingDetail /></ProtectedRoute>} />
          <Route path="/booking/:sailingId" element={<ProtectedRoute><BookingWizard /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="/partner/apply" element={<ProtectedRoute><PartnerApplication /></ProtectedRoute>} />

          <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
          <Route path="/admin/partners" element={<AdminRoute><PartnerManagement /></AdminRoute>} />
          <Route path="/admin/bookings/:reference" element={<AdminRoute><AdminBookingDetail /></AdminRoute>} />
          <Route path="/admin/:section" element={<AdminRoute><AdminResource /></AdminRoute>} />

          <Route path="/partner" element={<PartnerRoute><PartnerDashboard /></PartnerRoute>} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode><App /><ToastViewport /></React.StrictMode>
);
