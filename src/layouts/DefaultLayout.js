/**
 * Default Layout - Main application layout with sidebar and header
 */
import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { CContainer } from '@coreui/react';
import AppSidebar from './AppSidebar';
import AppHeader from './AppHeader';

const DefaultLayout = () => {
  const [sidebarShow, setSidebarShow] = useState(true);
  const [sidebarNarrow, setSidebarNarrow] = useState(true);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 993);

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 993; // 993px altında mobil mod
      setIsMobile(mobile);
      
      // Sidebar HER ZAMAN görünür - mobile'da narrow
      setSidebarShow(true);
      
      if (mobile) {
        // Mobile'da sidebar HER ZAMAN narrow
        setSidebarNarrow(true);
      }
    };

    handleResize(); // Initial check
    window.addEventListener('resize', handleResize);
    
    // Her 100ms kontrol et
    const interval = setInterval(handleResize, 100);
    
    return () => {
      window.removeEventListener('resize', handleResize);
      clearInterval(interval);
    };
  }, []);

  // Sidebar'ın hiçbir zaman kapanmaması için visibility kontrolü
  const handleSidebarVisibilityChange = (value) => {
    // Sidebar'ı ASLA kapatma
    setSidebarShow(true);
  };

  return (
    <div>
      <AppSidebar 
        visible={true} // Her zaman görünür
        onVisibleChange={handleSidebarVisibilityChange}
        narrow={isMobile ? true : sidebarNarrow}
        onNarrowChange={isMobile ? undefined : setSidebarNarrow}
        isMobile={isMobile}
      />
      <div className={`wrapper d-flex flex-column min-vh-100 bg-light ${(isMobile || sidebarNarrow) ? 'sidebar-narrow-wrapper' : 'sidebar-expanded-wrapper'}`}>
        <AppHeader />
        <div className="body flex-grow-1 px-3">
          <CContainer fluid>
            <Outlet />
          </CContainer>
        </div>
      </div>
    </div>
  );
};

export default DefaultLayout;
