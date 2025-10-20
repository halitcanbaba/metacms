/**
 * Private Route Component - Protect authenticated routes
 */
import React from 'react';
import { Navigate } from 'react-router-dom';
import { authService } from '../services/auth';

const PrivateRoute = ({ children }) => {
  return authService.isAuthenticated() ? children : <Navigate to="/login" />;
};

export default PrivateRoute;
