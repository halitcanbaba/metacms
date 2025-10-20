/**
 * Default Layout - Main application layout with sidebar and header
 */
import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { CContainer } from '@coreui/react';
import AppSidebar from './AppSidebar';
import AppHeader from './AppHeader';

const DefaultLayout = () => {
  const [sidebarShow, setSidebarShow] = useState(true);
  const [sidebarUnfoldable, setSidebarUnfoldable] = useState(false);

  return (
    <div>
      <AppSidebar 
        visible={sidebarShow}
        onVisibleChange={setSidebarShow}
        unfoldable={sidebarUnfoldable}
        onUnfoldableChange={setSidebarUnfoldable}
      />
      <div className="wrapper d-flex flex-column min-vh-100 bg-light">
        <AppHeader onToggleSidebar={() => setSidebarShow(!sidebarShow)} />
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
