/**
 * Theme Context - Dark mode only with custom dark gray background
 */
import React, { createContext, useContext, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children }) => {
  useEffect(() => {
    // Always set dark theme
    const root = document.documentElement;
    root.setAttribute('data-coreui-theme', 'dark');
    
    // Apply custom dark background color
    document.body.style.backgroundColor = '#1a1d21';
  }, []);

  return (
    <ThemeContext.Provider value={{ isDark: true }}>
      {children}
    </ThemeContext.Provider>
  );
};
