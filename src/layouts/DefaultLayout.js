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
  const [sidebarNarrow, setSidebarNarrow] = useState(false);

  return (
    <div>
      <AppSidebar 
        visible={sidebarShow}
        onVisibleChange={setSidebarShow}
        narrow={sidebarNarrow}
        onNarrowChange={setSidebarNarrow}
      />
      <div className="wrapper d-flex flex-column min-vh-100 bg-light">
        <AppHeader onToggleSidebar={() => setSidebarNarrow(!sidebarNarrow)} />
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
