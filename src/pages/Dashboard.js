/**
 * Dashboard Page - Overview statistics and recent activity
 */
import React, { useEffect, useState } from 'react';
import {
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CRow,
  CTable,
  CTableBody,
  CTableDataCell,
  CTableHead,
  CTableHeaderCell,
  CTableRow,
  CSpinner,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilPeople, cilWallet, cilCash, cilChart } from '@coreui/icons';
import { customersService } from '../services/customers';
import { accountsService } from '../services/accounts';

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalCustomers: 0,
    totalAccounts: 0,
    totalBalance: 0,
  });
  const [recentCustomers, setRecentCustomers] = useState([]);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);

      // Load customers
      const customersData = await customersService.getAll({ limit: 5 });
      console.log('Customers Data:', customersData);
      setRecentCustomers(customersData.items || []);
      
      // Load accounts
      const accountsData = await accountsService.getAll({ limit: 100 });
      console.log('Accounts Data:', accountsData);
      console.log('Accounts Items:', accountsData.items);
      
      // Calculate stats
      const accounts = accountsData.items || [];
      console.log('Processing accounts:', accounts);
      
      const totalBalance = accounts.reduce((sum, acc) => {
        console.log('Account balance:', acc.login, acc.balance);
        return sum + (parseFloat(acc.balance) || 0);
      }, 0);
      
      console.log('Total Balance:', totalBalance);
      
      setStats({
        totalCustomers: customersData.total || 0,
        totalAccounts: accountsData.total || 0,
        totalBalance: totalBalance,
      });
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const StatCard = ({ title, value, icon, color }) => (
    <CCol sm={6} lg={3}>
      <CCard className={`text-white bg-${color}`}>
        <CCardBody className="pb-0 d-flex justify-content-between align-items-start">
          <div>
            <div className="fs-4 fw-semibold">{value}</div>
            <div>{title}</div>
          </div>
          <CIcon icon={icon} size="xl" />
        </CCardBody>
      </CCard>
    </CCol>
  );

  if (loading) {
    return (
      <div className="text-center mt-5">
        <CSpinner color="primary" />
      </div>
    );
  }

  return (
    <>
      <h1 className="mb-4">Dashboard</h1>

      {/* Statistics Cards */}
      <CRow className="mb-4">
        <StatCard
          title="Total Customers"
          value={stats.totalCustomers}
          icon={cilPeople}
          color="primary"
        />
        <StatCard
          title="MT5 Accounts"
          value={stats.totalAccounts}
          icon={cilWallet}
          color="info"
        />
        <StatCard
          title="Total Balance"
          value={`$${stats.totalBalance.toFixed(2)}`}
          icon={cilCash}
          color="success"
        />
        <StatCard
          title="Active Positions"
          value="0"
          icon={cilChart}
          color="warning"
        />
      </CRow>

      {/* Recent Customers */}
      <CRow>
        <CCol>
          <CCard>
            <CCardHeader>
              <strong>Recent Customers</strong>
            </CCardHeader>
            <CCardBody>
              {recentCustomers.length === 0 ? (
                <p className="text-muted">No customers yet.</p>
              ) : (
                <CTable hover responsive>
                  <CTableHead>
                    <CTableRow>
                      <CTableHeaderCell>ID</CTableHeaderCell>
                      <CTableHeaderCell>Name</CTableHeaderCell>
                      <CTableHeaderCell>Email</CTableHeaderCell>
                      <CTableHeaderCell className="d-none d-md-table-cell">Phone</CTableHeaderCell>
                      <CTableHeaderCell className="d-none d-lg-table-cell">Created</CTableHeaderCell>
                    </CTableRow>
                  </CTableHead>
                  <CTableBody>
                    {recentCustomers.map((customer) => (
                      <CTableRow key={customer.id}>
                        <CTableDataCell>{customer.id}</CTableDataCell>
                        <CTableDataCell>{customer.name}</CTableDataCell>
                        <CTableDataCell>{customer.email}</CTableDataCell>
                        <CTableDataCell className="d-none d-md-table-cell">{customer.phone || '-'}</CTableDataCell>
                        <CTableDataCell className="d-none d-lg-table-cell">
                          {new Date(customer.created_at).toLocaleDateString()}
                        </CTableDataCell>
                      </CTableRow>
                    ))}
                  </CTableBody>
                </CTable>
              )}
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>
    </>
  );
};

export default Dashboard;
