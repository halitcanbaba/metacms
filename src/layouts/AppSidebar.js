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
      visible={visible}
      onVisibleChange={onVisibleChange}
      narrow={narrow}
      className={narrow ? 'sidebar-narrow' : ''}
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
