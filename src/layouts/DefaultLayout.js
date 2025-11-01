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
  const [isMobile, setIsMobile] = useState(window.innerWidth < 992);

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 992;
      setIsMobile(mobile);
      if (mobile) {
        // Mobile'da sidebar her zaman göster ve narrow yap
        setSidebarShow(true);
        setSidebarNarrow(true);
      } else {
        // Desktop'ta normal davranış
        setSidebarShow(true);
      }
    };

    handleResize(); // Initial check
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div>
      <AppSidebar 
        visible={sidebarShow}
        onVisibleChange={setSidebarShow}
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
