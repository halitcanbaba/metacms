/**
 * Daily PNL Page - View profit/loss metrics by account and institution
 */
import React, { useEffect, useState } from 'react';
import {
  CButton,
  CCard,
  CCardBody,
  CCol,
  CRow,
  CAlert,
  CTable,
  CTableBody,
  CTableDataCell,
  CTableHead,
  CTableHeaderCell,
  CTableRow,
  CSpinner,
  CNav,
  CNavItem,
  CNavLink,
  CTabContent,
  CTabPane,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilBuilding, cilReload, cilStar } from '@coreui/icons';
import api from '../services/api';

const DailyPnL = () => {
  const [activeTab, setActiveTab] = useState('winners');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // Monthly Top Winners state
  const [winners, setWinners] = useState([]);
  const [loadingWinners, setLoadingWinners] = useState(false);
  
  // Institution PNL state
  const [institutionDate, setInstitutionDate] = useState(
    new Date(new Date().setDate(new Date().getDate() - 1)).toISOString().split('T')[0]
  );
  const [institutionPnl, setInstitutionPnl] = useState(null);
  const [latestRecords, setLatestRecords] = useState([]);
  const [loadingLatest, setLoadingLatest] = useState(false);

  useEffect(() => {
    if (activeTab === 'winners') {
      loadWinners();
    } else if (activeTab === 'institution') {
      loadInstitutionPnl();
      loadLatestRecords();
    }
  }, [activeTab]);

  const loadWinners = async () => {
    try {
      setLoadingWinners(true);
      setError('');
      const response = await api.get('/api/reports/monthly-top-winners');
      setWinners(response.data.winners || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load monthly top winners');
      setWinners([]);
    } finally {
      setLoadingWinners(false);
    }
  };

  const loadInstitutionPnl = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await api.get('/api/accounts/daily-pnl', {
        params: { login: 0, target_date: institutionDate },
      });
      setInstitutionPnl(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load institution PNL');
      setInstitutionPnl(null);
    } finally {
      setLoading(false);
    }
  };

  const loadLatestRecords = async () => {
    try {
      setLoadingLatest(true);
      const response = await api.get('/api/reports/daily-pnl/latest', {
        params: { days: 30, login: 0 },
      });
      setLatestRecords(response.data.records || []);
    } catch (err) {
      console.error('Failed to load latest records:', err);
    } finally {
      setLoadingLatest(false);
    }
  };

  const formatCurrency = (value) => {
    if (value === null || value === undefined) return '0.00';
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  return (
    <CRow>
      <CCol xs={12}>
        <CCard className="mb-4">
          <CCardBody>
            {error && <CAlert color="danger" dismissible onClose={() => setError('')}>{error}</CAlert>}

            <div className="d-flex justify-content-between align-items-center">
              <CNav variant="tabs" role="tablist">
                <CNavItem>
                  <CNavLink
                    active={activeTab === 'winners'}
                    onClick={() => setActiveTab('winners')}
                    style={{ cursor: 'pointer' }}
                  >
                    <CIcon icon={cilStar} className="me-2" />
                    Monthly Top Winner
                  </CNavLink>
                </CNavItem>
                <CNavItem>
                  <CNavLink
                    active={activeTab === 'institution'}
                    onClick={() => setActiveTab('institution')}
                    style={{ cursor: 'pointer' }}
                  >
                    <CIcon icon={cilBuilding} className="me-2" />
                    Institution PNL
                  </CNavLink>
                </CNavItem>
              </CNav>
              
              {activeTab === 'institution' && (
                <CButton
                  color="success"
                  size="sm"
                  onClick={async () => {
                    setLoadingLatest(true);
                    setError('');
                    try {
                      await api.post('/api/reports/sync-daily-pnl', { target_date: institutionDate });
                      await loadLatestRecords();
                    } catch (err) {
                      setError(err.response?.data?.detail || 'Failed to sync daily PNL');
                    } finally {
                      setLoadingLatest(false);
                    }
                  }}
                  disabled={loadingLatest}
                  className="mb-2"
                >
                  {loadingLatest ? <CSpinner size="sm" /> : <CIcon icon={cilReload} />}
                </CButton>
              )}
            </div>

            <CTabContent className="mt-3">
              {/* Monthly Top Winner Tab */}
              <CTabPane visible={activeTab === 'winners'}>
                <CCard className="m-0">
                  <CCardBody className="p-3">
                    {loadingWinners ? (
                      <div className="text-center" style={{ padding: '20px' }}>
                        <CSpinner />
                      </div>
                    ) : winners.length > 0 ? (
                      <div style={{ overflowX: 'auto' }}>
                        <CTable bordered striped hover>
                          <CTableHead color="dark">
                            <CTableRow>
                              <CTableHeaderCell className="text-center" style={{ width: '80px' }}>Rank</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ width: '120px' }}>Login</CTableHeaderCell>
                              <CTableHeaderCell>Customer Name</CTableHeaderCell>
                              <CTableHeaderCell className="text-end" style={{ width: '150px' }}>Net P&L</CTableHeaderCell>
                            </CTableRow>
                          </CTableHead>
                          <CTableBody>
                            {winners.map((winner) => (
                              <CTableRow key={winner.login}>
                                <CTableDataCell className="text-center">
                                  {winner.rank === 1 && <CIcon icon={cilStar} className="me-1" style={{ color: '#FFD700' }} />}
                                  {winner.rank === 2 && <CIcon icon={cilStar} className="me-1" style={{ color: '#C0C0C0' }} />}
                                  {winner.rank === 3 && <CIcon icon={cilStar} className="me-1" style={{ color: '#CD7F32' }} />}
                                  {winner.rank}
                                </CTableDataCell>
                                <CTableDataCell className="text-center">{winner.login}</CTableDataCell>
                                <CTableDataCell>{winner.customer_name}</CTableDataCell>
                                <CTableDataCell className="text-end">
                                  <span style={{ color: winner.total_net_pnl >= 0 ? '#2eb85c' : '#e55353', fontWeight: '500' }}>
                                    {winner.total_net_pnl >= 0 ? '+' : ''}{winner.total_net_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </span>
                                </CTableDataCell>
                              </CTableRow>
                            ))}
                          </CTableBody>
                        </CTable>
                      </div>
                    ) : (
                      <div className="text-center text-muted" style={{ padding: '40px' }}>
                        <CIcon icon={cilStar} size="3xl" className="mb-3" style={{ opacity: 0.3 }} />
                        <p>No data available for current month</p>
                      </div>
                    )}
                  </CCardBody>
                </CCard>
              </CTabPane>

              {/* Institution PNL Tab */}
              <CTabPane visible={activeTab === 'institution'}>
                {/* Latest 30 Days History - Excel Style */}
                <CCard className="m-0">
                  <CCardBody className="p-0 m-0">
                    {loadingLatest ? (
                      <div className="text-center" style={{ padding: '20px' }}>
                        <CSpinner />
                      </div>
                    ) : latestRecords.length > 0 ? (
                      <div style={{ overflowX: 'auto' }}>
                        <CTable bordered striped small style={{ fontSize: '0.875rem' }}>
                          <CTableHead color="dark">
                            <CTableRow>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '80px' }}>Day</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Deposit</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>WD</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Net Dep</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Promotion</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Credit</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>T.Prom</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Total IB</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Commission</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Swap</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Closed Pnl.</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Equity Pnl.</CTableHeaderCell>
                              <CTableHeaderCell className="text-center" style={{ minWidth: '100px' }}>Net Pnl.</CTableHeaderCell>
                            </CTableRow>
                          </CTableHead>
                          <CTableBody>
                            {latestRecords.map((record, index) => (
                              <CTableRow key={index}>
                                <CTableDataCell className="text-center">{record.day}</CTableDataCell>
                                <CTableDataCell className="text-center">{formatCurrency(record.deposit)}</CTableDataCell>
                                <CTableDataCell className="text-center">{formatCurrency(record.withdrawal)}</CTableDataCell>
                                <CTableDataCell className="text-center" style={{ fontWeight: '500' }}>
                                  {formatCurrency(record.net_deposit)}
                                </CTableDataCell>
                                <CTableDataCell className="text-center">{formatCurrency(record.promotion)}</CTableDataCell>
                                <CTableDataCell className="text-center">{formatCurrency(record.credit)}</CTableDataCell>
                                <CTableDataCell className="text-center" style={{ fontWeight: '500' }}>
                                  {formatCurrency(record.net_credit_promotion)}
                                </CTableDataCell>
                                <CTableDataCell className="text-center" style={{ fontWeight: '500' }}>
                                  {formatCurrency(record.total_ib)}
                                </CTableDataCell>
                                <CTableDataCell className="text-center">{formatCurrency(record.commission)}</CTableDataCell>
                                <CTableDataCell className="text-center">{formatCurrency(record.swap)}</CTableDataCell>
                                <CTableDataCell className="text-center">{formatCurrency(record.closed_pnl)}</CTableDataCell>
                                <CTableDataCell className="text-center" style={{ fontWeight: '500' }}>
                                  {formatCurrency(record.equity_pnl)}
                                </CTableDataCell>
                                <CTableDataCell className="text-center" style={{ fontWeight: '500' }}>
                                  {formatCurrency(record.net_pnl)}
                                </CTableDataCell>
                              </CTableRow>
                            ))}
                          </CTableBody>
                        </CTable>
                      </div>
                    ) : (
                      <CAlert color="info">No historical data available</CAlert>
                    )}
                  </CCardBody>
                </CCard>
              </CTabPane>
            </CTabContent>
          </CCardBody>
        </CCard>
      </CCol>
    </CRow>
  );
};

export default DailyPnL;
