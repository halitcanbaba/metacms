/**
 * Main App Component with Routing
 */
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import '@coreui/coreui/dist/css/coreui.min.css';
import './App.css';

// Context
import { ThemeProvider } from './contexts/ThemeContext';

// Components
import PrivateRoute from './components/PrivateRoute';
import DefaultLayout from './layouts/DefaultLayout';

// Pages
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import Agents from './pages/Agents';
import Accounts from './pages/Accounts';
import AccountDetail from './pages/AccountDetail';
import Balance from './pages/Balance';
import Positions from './pages/Positions';
import Audit from './pages/Audit';
import DailyPnL from './pages/DailyPnL';
import Users from './pages/Users';

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<Login />} />

        {/* Protected Routes */}
        <Route
          path="/"
          element={
            <PrivateRoute>
              <DefaultLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="customers" element={<Customers />} />
          <Route path="agents" element={<Agents />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="account/:login" element={<AccountDetail />} />
          <Route path="balance" element={<Balance />} />
          <Route path="positions" element={<Positions />} />
          <Route path="daily-pnl" element={<DailyPnL />} />
          <Route path="audit" element={<Audit />} />
          <Route path="users" element={<Users />} />
        </Route>

        {/* 404 */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
