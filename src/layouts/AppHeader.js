/**
 * Application Header
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CContainer,
  CHeader,
  CHeaderBrand,
  CHeaderNav,
  CNavLink,
  CNavItem,
  CDropdown,
  CDropdownToggle,
  CDropdownMenu,
  CDropdownItem,
  CDropdownDivider,
  CFormInput,
  CInputGroup,
  CInputGroupText,
  CButton,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilAccountLogout, cilUser, cilPeople, cilSearch } from '@coreui/icons';
import { authService } from '../services/auth';

const AppHeader = () => {
  const navigate = useNavigate();
  const user = authService.getCurrentUser();
  const [searchLogin, setSearchLogin] = useState('');

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchLogin.trim()) {
      navigate(`/account/${searchLogin.trim()}`);
      setSearchLogin('');
    }
  };

  return (
    <CHeader position="sticky" className="mb-4">
      <CContainer fluid>
        <CHeaderNav>
          <form onSubmit={handleSearch}>
            <CInputGroup size="sm" style={{ maxWidth: '200px' }}>
              <CInputGroupText>
                <CIcon icon={cilSearch} size="sm" />
              </CInputGroupText>
              <CFormInput
                type="text"
                placeholder="Search..."
                value={searchLogin}
                onChange={(e) => setSearchLogin(e.target.value)}
              />
            </CInputGroup>
          </form>
        </CHeaderNav>

        <CHeaderNav className="ms-auto">
          <CDropdown variant="nav-item">
            <CDropdownToggle placement="bottom-end" className="py-0" caret={false}>
              <CIcon icon={cilUser} size="lg" />
              <span className="ms-2 d-none d-sm-inline">{user?.email || 'User'}</span>
            </CDropdownToggle>
            <CDropdownMenu className="pt-0" placement="bottom-end">
              <CDropdownItem>
                <CIcon icon={cilUser} className="me-2" />
                Profile
              </CDropdownItem>
              <CDropdownItem onClick={() => navigate('/users')}>
                <CIcon icon={cilPeople} className="me-2" />
                Manage Users
              </CDropdownItem>
              <CDropdownDivider />
              <CDropdownItem onClick={handleLogout}>
                <CIcon icon={cilAccountLogout} className="me-2" />
                Logout
              </CDropdownItem>
            </CDropdownMenu>
          </CDropdown>
        </CHeaderNav>
      </CContainer>
    </CHeader>
  );
};

export default AppHeader;
