/**
 * Dashboard Page - Overview statistics and recent activity
 */
import React, { useEffect, useState, useRef } from 'react';
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
  CBadge,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import {
  cilPeople,
  cilMoney,
  cilArrowTop,
  cilArrowBottom,
  cilChart,
  cilWallet,
} from '@coreui/icons';
import { customersService } from '../services/customers';
import { accountsService } from '../services/accounts';
import api from '../services/api';

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalCustomers: 0,
    totalAccounts: 0,
    totalEquity: 0,
    totalBalance: 0,
    netProfit: 0,
    activePositions: 0,
    totalVolume: 0,
    totalCommission: 0,
    totalSwap: 0,
    closedProfit: 0,
    totalDeposit: 0,
    totalWithdrawal: 0,
    netDeposit: 0,
  });
  const [recentCustomers, setRecentCustomers] = useState([]);
  const [positions, setPositions] = useState([]);
  const [marginCallAccounts, setMarginCallAccounts] = useState([]);
  
  // WebSocket refs
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {
    loadDashboardData();
    
    // Start WebSocket connection for real-time updates
    connectWebSocket();
    
    return () => {
      // Cleanup WebSocket on unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, []);

  const connectWebSocket = () => {
    // Get WebSocket URL from API URL
    const wsUrl = process.env.REACT_APP_API_URL 
      ? process.env.REACT_APP_API_URL.replace('http', 'ws').replace('https', 'wss')
      : 'ws://localhost:8000';
    
    const ws = new WebSocket(`${wsUrl}/ws/dashboard`);
    wsRef.current = ws;
    
    ws.onopen = () => {
      console.log('Dashboard WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'dashboard_update') {
          // Update stats from WebSocket data
          setStats(prevStats => ({
            ...prevStats,
            totalEquity: data.stats.total_equity || 0,
            totalBalance: data.stats.total_balance || 0,
            netProfit: data.stats.total_floating_profit || 0,
            activePositions: data.stats.active_positions || 0,
            totalVolume: data.stats.total_volume || 0,
          }));
          
          // Update margin call accounts
          if (data.margin_calls) {
            setMarginCallAccounts(data.margin_calls);
          }
          
          // Update positions (limit to 50 most recent)
          if (data.positions) {
            setPositions(data.positions);
          }
        } else if (data.error) {
          console.error('Dashboard WebSocket error:', data.error);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
    
    ws.onerror = (error) => {
      console.error('Dashboard WebSocket error:', error);
    };
    
    ws.onclose = (event) => {
      console.log('Dashboard WebSocket closed', event.code, event.reason);
      
      // Try to reconnect after 2 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('Reconnecting Dashboard WebSocket...');
        connectWebSocket();
      }, 2000);
    };
  };

  const loadDashboardData = async () => {
    try {
      setLoading(true);

      // Load customers
      const customersData = await customersService.getAll({ limit: 5 });
      setRecentCustomers(customersData.items || []);
      
      // Load all accounts to calculate equity
      const accountsData = await accountsService.getAll({ limit: 1000 });
      const accounts = accountsData.items || [];
      
      // Load realtime data for all accounts
      const realtimeResponse = await api.get('/api/accounts/realtime');
      const realtimeData = realtimeResponse.data || [];
      
      // Load all open positions
      const positionsResponse = await api.get('/api/positions/open');
      const allPositions = positionsResponse.data?.positions || [];
      setPositions(allPositions);
      
      // Load today's daily PnL data for deposit/withdrawal info
      const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD format
      let totalDeposit = 0;
      let totalWithdrawal = 0;
      let netDeposit = 0;
      let pnlData = [];
      
      try {
        const pnlResponse = await api.get(`/api/reports/daily-pnl?date=${today}`);
        pnlData = pnlResponse.data || [];
        
        // Calculate totals from all accounts
        totalDeposit = pnlData.reduce((sum, pnl) => sum + (parseFloat(pnl.deposit) || 0), 0);
        totalWithdrawal = pnlData.reduce((sum, pnl) => sum + (parseFloat(pnl.withdrawal) || 0), 0);
        netDeposit = pnlData.reduce((sum, pnl) => sum + (parseFloat(pnl.net_deposit) || 0), 0);
      } catch (error) {
        console.warn('Could not load deposit/withdrawal data:', error);
      }
      
      // Calculate statistics
      const totalBalance = accounts.reduce((sum, acc) => sum + (parseFloat(acc.balance) || 0), 0);
      const totalEquity = realtimeData.reduce((sum, rt) => sum + (parseFloat(rt.equity) || 0), 0);
      
      // Calculate net profit, volume, commission, and swap from positions
      const netProfit = allPositions.reduce((sum, pos) => sum + (parseFloat(pos.profit) || 0), 0);
      const totalVolume = allPositions.reduce((sum, pos) => sum + (parseFloat(pos.volume) || 0), 0);
      const totalCommission = allPositions.reduce((sum, pos) => sum + (parseFloat(pos.commission) || 0), 0);
      const totalSwap = allPositions.reduce((sum, pos) => sum + (parseFloat(pos.swap) || 0), 0);
      
      // Get today's closed profit from daily PnL (if available)
      let closedProfit = 0;
      if (pnlData && pnlData.length > 0) {
        closedProfit = pnlData.reduce((sum, pnl) => sum + (parseFloat(pnl.closed_pnl) || 0), 0);
      }
      
      // Find accounts with margin level below 100%
      const marginCallList = [];
      for (const rtData of realtimeData) {
        const equity = parseFloat(rtData.equity) || 0;
        const margin = parseFloat(rtData.margin) || 0;
        
        // Calculate margin level: (Equity / Margin) * 100
        if (margin > 0) {
          const marginLevel = (equity / margin) * 100;
          
          // If margin level is below 100%, add to margin call list
          if (marginLevel < 100) {
            // Find account info
            const accountInfo = accounts.find(acc => acc.login === rtData.login);
            
            marginCallList.push({
              login: rtData.login,
              name: accountInfo?.name || accountInfo?.customer?.name || 'N/A',
              equity: equity,
              margin: margin,
              marginLevel: marginLevel,
              freeMargin: parseFloat(rtData.margin_free) || 0,
            });
          }
        }
      }
      
      // Sort by margin level (lowest first - most critical)
      marginCallList.sort((a, b) => a.marginLevel - b.marginLevel);
      setMarginCallAccounts(marginCallList);
      
      setStats({
        totalCustomers: customersData.total || 0,
        totalAccounts: accountsData.total || 0,
        totalEquity: totalEquity,
        totalBalance: totalBalance,
        netProfit: netProfit,
        activePositions: allPositions.length,
        totalVolume: totalVolume,
        totalCommission: totalCommission,
        totalSwap: totalSwap,
        closedProfit: closedProfit,
        totalDeposit: totalDeposit,
        totalWithdrawal: totalWithdrawal,
        netDeposit: netDeposit,
      });
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'decimal',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value || 0);
  };

  const formatVolume = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'decimal',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value || 0);
  };

  const StatCard = ({ title, value, icon, color, subtitle }) => (
    <CCol sm={6} lg={3}>
      <CCard className={`text-white bg-${color} mb-4`}>
        <CCardBody className="d-flex justify-content-between align-items-start">
          <div>
            <div className="fs-4 fw-semibold">{value}</div>
            <div className="text-white-50">{title}</div>
            {subtitle && <small className="text-white-75">{subtitle}</small>}
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
      {/* Main Statistics Cards */}
      <CRow>
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
          title="Net Equity"
          value={`$${formatCurrency(stats.totalEquity)}`}
          subtitle={`Balance: $${formatCurrency(stats.totalBalance)}`}
          icon={cilMoney}
          color="success"
        />
        <StatCard
          title="Active Positions"
          value={stats.activePositions}
          subtitle={`P/L: $${formatCurrency(stats.netProfit)}`}
          icon={cilChart}
          color={stats.netProfit >= 0 ? 'success' : 'danger'}
        />
      </CRow>

      {/* Trading Statistics */}
      <CRow>
        <CCol lg={6}>
          <CCard className="mb-4">
            <CCardHeader>
              <strong>Trading Statistics (Today)</strong>
            </CCardHeader>
            <CCardBody>
              <CTable small borderless>
                <CTableBody>
                  <CTableRow>
                    <CTableDataCell className="text-medium-emphasis">Closed Profit</CTableDataCell>
                    <CTableDataCell className={`text-end fw-semibold text-${stats.closedProfit >= 0 ? 'success' : 'danger'}`}>
                      ${formatCurrency(stats.closedProfit)}
                    </CTableDataCell>
                  </CTableRow>
                  <CTableRow>
                    <CTableDataCell className="text-medium-emphasis">Total Volume</CTableDataCell>
                    <CTableDataCell className="text-end fw-semibold">
                      {formatVolume(stats.totalVolume)} lots
                    </CTableDataCell>
                  </CTableRow>
                  <CTableRow>
                    <CTableDataCell className="text-medium-emphasis">Total Commission</CTableDataCell>
                    <CTableDataCell className={`text-end fw-semibold text-${stats.totalCommission >= 0 ? 'secondary' : 'danger'}`}>
                      ${formatCurrency(stats.totalCommission)}
                    </CTableDataCell>
                  </CTableRow>
                  <CTableRow>
                    <CTableDataCell className="text-medium-emphasis">Total Swap</CTableDataCell>
                    <CTableDataCell className={`text-end fw-semibold text-${stats.totalSwap >= 0 ? 'success' : 'danger'}`}>
                      ${formatCurrency(stats.totalSwap)}
                    </CTableDataCell>
                  </CTableRow>
                  <CTableRow>
                    <CTableDataCell colSpan={2}><hr className="my-2" /></CTableDataCell>
                  </CTableRow>
                  <CTableRow>
                    <CTableDataCell className="text-medium-emphasis">Deposits</CTableDataCell>
                    <CTableDataCell className="text-end fw-semibold text-success">
                      ${formatCurrency(stats.totalDeposit)}
                    </CTableDataCell>
                  </CTableRow>
                  <CTableRow>
                    <CTableDataCell className="text-medium-emphasis">Withdrawals</CTableDataCell>
                    <CTableDataCell className="text-end fw-semibold text-danger">
                      ${formatCurrency(stats.totalWithdrawal)}
                    </CTableDataCell>
                  </CTableRow>
                  <CTableRow>
                    <CTableDataCell className="text-medium-emphasis">Net Deposit</CTableDataCell>
                    <CTableDataCell className={`text-end fw-semibold text-${stats.netDeposit >= 0 ? 'success' : 'danger'}`}>
                      ${formatCurrency(stats.netDeposit)}
                    </CTableDataCell>
                  </CTableRow>
                </CTableBody>
              </CTable>
            </CCardBody>
          </CCard>
        </CCol>

        <CCol lg={6}>
          <CCard className="mb-4">
            <CCardHeader>
              <strong>Margin Call Alerts</strong>
              {marginCallAccounts.length > 0 && (
                <CBadge color="danger" className="ms-2">
                  {marginCallAccounts.length}
                </CBadge>
              )}
            </CCardHeader>
            <CCardBody>
              {marginCallAccounts.length === 0 ? (
                <div className="text-center text-medium-emphasis py-5">
                  <CIcon icon={cilChart} size="3xl" className="mb-3 opacity-25" />
                  <p className="mb-0">No margin call alerts at this time</p>
                  <small>Accounts with margin level below 100% will appear here</small>
                </div>
              ) : (
                <CTable hover responsive small>
                  <CTableHead>
                    <CTableRow>
                      <CTableHeaderCell>Login</CTableHeaderCell>
                      <CTableHeaderCell>Name</CTableHeaderCell>
                      <CTableHeaderCell>Equity</CTableHeaderCell>
                      <CTableHeaderCell>Margin</CTableHeaderCell>
                      <CTableHeaderCell>Margin Level</CTableHeaderCell>
                    </CTableRow>
                  </CTableHead>
                  <CTableBody>
                    {marginCallAccounts.slice(0, 10).map((account) => (
                      <CTableRow key={account.login}>
                        <CTableDataCell className="fw-semibold">
                          {account.login}
                        </CTableDataCell>
                        <CTableDataCell>{account.name}</CTableDataCell>
                        <CTableDataCell>${formatCurrency(account.equity)}</CTableDataCell>
                        <CTableDataCell>${formatCurrency(account.margin)}</CTableDataCell>
                        <CTableDataCell>
                          <CBadge 
                            color={
                              account.marginLevel < 50 ? 'danger' : 
                              account.marginLevel < 80 ? 'warning' : 
                              'info'
                            }
                          >
                            {account.marginLevel.toFixed(2)}%
                          </CBadge>
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
