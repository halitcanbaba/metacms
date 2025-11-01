/**
 * Application Sidebar - Navigation menu
 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  CSidebar,
  CSidebarBrand,
  CSidebarNav,
  CNavItem,
  CSidebarToggler,
  CButton,
  CTooltip,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import {
  cilSpeedometer,
  cilPeople,
  cilUser,
  cilWallet,
  cilCash,
  cilChart,
  cilMoney,
  cilHistory,
  cilMenu,
} from '@coreui/icons';

const AppSidebar = ({ visible, onVisibleChange, narrow, onNarrowChange, isMobile }) => {
  const navigate = useNavigate();
  const location = useLocation();

  // Force sidebar to always be visible - DOM manipulation as last resort
  React.useEffect(() => {
    const forceSidebarVisible = () => {
      const sidebar = document.querySelector('.sidebar');
      if (sidebar) {
        // CoreUI style'larını agresif override
        sidebar.style.setProperty('display', 'block', 'important');
        sidebar.style.setProperty('visibility', 'visible', 'important');
        sidebar.style.setProperty('opacity', '1', 'important');
        sidebar.style.setProperty('transform', 'translateX(0)', 'important');
        sidebar.style.setProperty('left', '0', 'important');
        sidebar.style.setProperty('position', 'fixed', 'important');
        sidebar.style.setProperty('background-color', '#212631', 'important');
        sidebar.style.setProperty('margin-inline-start', '0', 'important');
        sidebar.style.setProperty('margin-left', '0', 'important');
        
        // Class'ları da zorla
        if (!sidebar.classList.contains('sidebar-show')) {
          sidebar.classList.add('sidebar-show');
        }
        sidebar.classList.remove('sidebar-hide');
      }
    };

    // Run immediately and on very frequent interval
    forceSidebarVisible();
    const interval = setInterval(forceSidebarVisible, 50); // Her 50ms
    
    // Resize ve scroll event'lerinde de çalıştır
    window.addEventListener('resize', forceSidebarVisible);
    window.addEventListener('scroll', forceSidebarVisible);

    return () => {
      clearInterval(interval);
      window.removeEventListener('resize', forceSidebarVisible);
      window.removeEventListener('scroll', forceSidebarVisible);
    };
  }, []);

  const navItems = [
    {
      title: 'Dashboard',
      to: '/dashboard',
      icon: cilSpeedometer,
    },
    {
      title: 'Agents',
      to: '/agents',
      icon: cilUser,
    },
    {
      title: 'Customers',
      to: '/customers',
      icon: cilPeople,
    },
    {
      title: 'MT5 Accounts',
      to: '/accounts',
      icon: cilWallet,
    },
    {
      title: 'Balance Operations',
      to: '/balance',
      icon: cilCash,
    },
    {
      title: 'Positions',
      to: '/positions',
      icon: cilChart,
    },
    {
      title: 'Daily P&L',
      to: '/daily-pnl',
      icon: cilMoney,
    },
    {
      title: 'Audit Logs',
      to: '/audit',
      icon: cilHistory,
    },
  ];

  const handleToggleNarrow = () => {
    if (onNarrowChange) {
      onNarrowChange(!narrow);
    }
  };

  return (
    <CSidebar 
      position="fixed"
      visible={true} // Her zaman görünür
      onVisibleChange={(val) => {
        // Mobile'da sidebar'ı kapatmaya izin verme
        if (!isMobile && onVisibleChange) {
          onVisibleChange(val);
        }
      }}
      narrow={narrow}
      unfoldable={false} // Otomatik açılma/kapanma kapalı
      className={`sidebar-show ${narrow ? 'sidebar-narrow' : ''}`}
      style={{ 
        display: 'block',
        visibility: 'visible',
        opacity: 1,
        transform: 'translateX(0)',
        left: 0,
        position: 'fixed',
        backgroundColor: '#212631'
      }}
    >
      {/* Toggle button sadece desktop'ta göster */}
      {!isMobile && onNarrowChange && (
        <div className="sidebar-header d-flex align-items-center justify-content-end p-3">
          <CButton
            color="link"
            className="text-white p-0"
            onClick={handleToggleNarrow}
            style={{ fontSize: '1.5rem' }}
          >
            <CIcon icon={cilMenu} size="lg" />
          </CButton>
        </div>
      )}
      
      <CSidebarNav>
        {navItems.map((item) => {
          const navItem = (
            <CNavItem
              href="#"
              onClick={(e) => {
                e.preventDefault();
                navigate(item.to);
              }}
              active={location.pathname === item.to}
            >
              <CIcon customClassName="nav-icon" icon={item.icon} />
              {!narrow && <span className="nav-text">{item.title}</span>}
            </CNavItem>
          );

          // Only show tooltip when sidebar is narrow
          return narrow ? (
            <CTooltip
              key={item.to}
              content={item.title}
              placement="right"
            >
              {navItem}
            </CTooltip>
          ) : (
            <div key={item.to}>{navItem}</div>
          );
        })}
      </CSidebarNav>
    </CSidebar>
  );
};

export default AppSidebar;
