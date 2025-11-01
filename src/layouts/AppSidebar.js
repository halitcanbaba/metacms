/**
 * Application Sidebar - Navigation menu
 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  CSidebar,
  CSidebarBrand,
  CSidebarNav,
  CNavTitle,
  CNavItem,
  CSidebarToggler,
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
} from '@coreui/icons';

const AppSidebar = ({ visible, onVisibleChange, unfoldable, onUnfoldableChange }) => {
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

  return (
    <CSidebar 
      position="fixed"
      visible={visible}
      onVisibleChange={onVisibleChange}
      unfoldable={unfoldable}
    >
      <CSidebarBrand className="d-none d-md-flex">
        <h4 className="text-white mb-0">CRM MT5</h4>
      </CSidebarBrand>

      <CSidebarNav>
        <CNavTitle>Navigation</CNavTitle>
        {navItems.map((item) => (
          <CNavItem
            key={item.to}
            href="#"
            onClick={(e) => {
              e.preventDefault();
              navigate(item.to);
            }}
            active={location.pathname === item.to}
          >
            <CIcon customClassName="nav-icon" icon={item.icon} />
            {item.title}
          </CNavItem>
        ))}
      </CSidebarNav>

      <CSidebarToggler 
        className="d-none d-lg-flex" 
        onClick={() => onUnfoldableChange(!unfoldable)}
      />
    </CSidebar>
  );
};

export default AppSidebar;
