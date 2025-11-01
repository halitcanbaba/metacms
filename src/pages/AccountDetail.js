import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CRow,
  CTable,
  CTableHead,
  CTableRow,
  CTableHeaderCell,
  CTableBody,
  CTableDataCell,
  CButton,
  CSpinner,
  CBadge,
  CAlert,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilArrowLeft, cilReload, cilWallet, cilChart, cilMoney } from '@coreui/icons';
import api from '../services/api';

const AccountDetail = () => {
  const { login } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [accountInfo, setAccountInfo] = useState(null);
  const [positions, setPositions] = useState([]);
  const [realtimeData, setRealtimeData] = useState(null);

  useEffect(() => {
    fetchAccountData();
  }, [login]);

  const fetchAccountData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch account basic info
      const accountResponse = await api.get(`/api/accounts/${login}`);
      setAccountInfo(accountResponse.data);

      // Fetch open positions
      const positionsResponse = await api.get(`/api/accounts/positions/account/${login}`);
      setPositions(positionsResponse.data || []);

      // Fetch realtime data
      const realtimeResponse = await api.get(`/api/accounts/realtime?login=${login}`);
      if (realtimeResponse.data && realtimeResponse.data.length > 0) {
        setRealtimeData(realtimeResponse.data[0]);
      }
    } catch (err) {
      console.error('Error fetching account data:', err);
      setError(err.response?.data?.detail || 'Failed to load account data');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAccountData();
    setRefreshing(false);
  };

  const calculateNetPosition = () => {
    if (!positions || positions.length === 0) return { profit: 0, volume: 0 };
    
    const totalProfit = positions.reduce((sum, pos) => sum + (pos.profit || 0), 0);
    const totalVolume = positions.reduce((sum, pos) => sum + (pos.volume || 0), 0);
    
    return { profit: totalProfit, volume: totalVolume };
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

  const getPositionTypeBadge = (type) => {
    return type === 0 ? (
      <CBadge color="success">Buy</CBadge>
    ) : (
      <CBadge color="danger">Sell</CBadge>
    );
  };

  const getProfitColor = (profit) => {
    if (profit > 0) return 'success';
    if (profit < 0) return 'danger';
    return 'secondary';
  };

  if (loading) {
    return (
      <CRow>
        <CCol xs={12}>
          <CCard>
            <CCardBody className="text-center py-5">
              <CSpinner color="primary" />
              <div className="mt-3">Loading account data...</div>
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>
    );
  }

  if (error) {
    return (
      <CRow>
        <CCol xs={12}>
          <CCard>
            <CCardBody>
              <CAlert color="danger">
                <h4>Error</h4>
                {error}
              </CAlert>
              <CButton color="primary" onClick={() => navigate('/accounts')}>
                <CIcon icon={cilArrowLeft} className="me-2" />
                Back to Accounts
              </CButton>
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>
    );
  }

  const netPosition = calculateNetPosition();
  const equity = realtimeData?.equity || accountInfo?.balance || 0;
  const balance = accountInfo?.balance || 0;
  const credit = accountInfo?.credit || 0;
  const margin = realtimeData?.margin || 0;
  const freeMargin = realtimeData?.free_margin || (equity - margin);
  const marginLevel = margin > 0 ? ((equity / margin) * 100) : 0;

  return (
    <CRow>
      <CCol xs={12}>
        <div className="d-flex justify-content-between align-items-center mb-3">
          <div>
            <CButton color="light" onClick={() => navigate('/accounts')} className="me-2">
              <CIcon icon={cilArrowLeft} className="me-2" />
              Back
            </CButton>
            <h4 className="d-inline-block mb-0">Account {login}</h4>
          </div>
          <CButton
            color="primary"
            variant="outline"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <CIcon icon={cilReload} className={refreshing ? 'rotating' : ''} />
            {refreshing ? ' Refreshing...' : ' Refresh'}
          </CButton>
        </div>
      </CCol>

      {/* Account Summary Cards */}
      <CCol xs={12} md={6} lg={3}>
        <CCard className="mb-4">
          <CCardBody>
            <div className="d-flex align-items-center">
              <CIcon icon={cilWallet} size="xl" className="me-3 text-primary" />
              <div>
                <div className="text-medium-emphasis small">Balance</div>
                <div className="fs-5 fw-semibold">${formatCurrency(balance)}</div>
              </div>
            </div>
          </CCardBody>
        </CCard>
      </CCol>

      <CCol xs={12} md={6} lg={3}>
        <CCard className="mb-4">
          <CCardBody>
            <div className="d-flex align-items-center">
              <CIcon icon={cilChart} size="xl" className="me-3 text-success" />
              <div>
                <div className="text-medium-emphasis small">Equity</div>
                <div className="fs-5 fw-semibold">${formatCurrency(equity)}</div>
              </div>
            </div>
          </CCardBody>
        </CCard>
      </CCol>

      <CCol xs={12} md={6} lg={3}>
        <CCard className="mb-4">
          <CCardBody>
            <div className="d-flex align-items-center">
              <CIcon icon={cilMoney} size="xl" className="me-3 text-warning" />
              <div>
                <div className="text-medium-emphasis small">Free Margin</div>
                <div className="fs-5 fw-semibold">${formatCurrency(freeMargin)}</div>
              </div>
            </div>
          </CCardBody>
        </CCard>
      </CCol>

      <CCol xs={12} md={6} lg={3}>
        <CCard className="mb-4">
          <CCardBody>
            <div className="d-flex align-items-center">
              <div className="me-3">
                <CBadge color={getProfitColor(netPosition.profit)} style={{ fontSize: '1.5rem', padding: '0.5rem' }}>
                  P/L
                </CBadge>
              </div>
              <div>
                <div className="text-medium-emphasis small">Net Position</div>
                <div className={`fs-5 fw-semibold text-${getProfitColor(netPosition.profit)}`}>
                  ${formatCurrency(netPosition.profit)}
                </div>
              </div>
            </div>
          </CCardBody>
        </CCard>
      </CCol>

      {/* Account Details */}
      <CCol xs={12} lg={6}>
        <CCard className="mb-4">
          <CCardHeader>
            <strong>Account Information</strong>
          </CCardHeader>
          <CCardBody>
            <CTable small>
              <CTableBody>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Login</CTableDataCell>
                  <CTableDataCell className="fw-semibold">{accountInfo?.login}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Name</CTableDataCell>
                  <CTableDataCell>{accountInfo?.customer_name || accountInfo?.name || '-'}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Group</CTableDataCell>
                  <CTableDataCell>{accountInfo?.group || accountInfo?.group_name || '-'}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Status</CTableDataCell>
                  <CTableDataCell>
                    <CBadge color={accountInfo?.status === 'active' ? 'success' : 'secondary'}>
                      {accountInfo?.status || 'unknown'}
                    </CBadge>
                  </CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Balance</CTableDataCell>
                  <CTableDataCell className="fw-semibold">${formatCurrency(balance)}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Credit</CTableDataCell>
                  <CTableDataCell>${formatCurrency(credit)}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Equity</CTableDataCell>
                  <CTableDataCell className="fw-semibold">${formatCurrency(equity)}</CTableDataCell>
                </CTableRow>
              </CTableBody>
            </CTable>
          </CCardBody>
        </CCard>
      </CCol>

      <CCol xs={12} lg={6}>
        <CCard className="mb-4">
          <CCardHeader>
            <strong>Margin Information</strong>
          </CCardHeader>
          <CCardBody>
            <CTable small>
              <CTableBody>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Margin</CTableDataCell>
                  <CTableDataCell className="fw-semibold">${formatCurrency(margin)}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Free Margin</CTableDataCell>
                  <CTableDataCell className="fw-semibold">${formatCurrency(freeMargin)}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Margin Level</CTableDataCell>
                  <CTableDataCell className="fw-semibold">{formatCurrency(marginLevel)}%</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Open Positions</CTableDataCell>
                  <CTableDataCell className="fw-semibold">{positions.length}</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Total Volume</CTableDataCell>
                  <CTableDataCell className="fw-semibold">{formatVolume(netPosition.volume)} lots</CTableDataCell>
                </CTableRow>
                <CTableRow>
                  <CTableDataCell className="text-medium-emphasis">Floating P/L</CTableDataCell>
                  <CTableDataCell className={`fw-semibold text-${getProfitColor(netPosition.profit)}`}>
                    ${formatCurrency(netPosition.profit)}
                  </CTableDataCell>
                </CTableRow>
              </CTableBody>
            </CTable>
          </CCardBody>
        </CCard>
      </CCol>

      {/* Open Positions */}
      <CCol xs={12}>
        <CCard>
          <CCardHeader>
            <strong>Open Positions ({positions.length})</strong>
          </CCardHeader>
          <CCardBody>
            {positions.length === 0 ? (
              <div className="text-center text-medium-emphasis py-4">
                No open positions
              </div>
            ) : (
              <CTable striped hover responsive>
                <CTableHead>
                  <CTableRow>
                    <CTableHeaderCell>Ticket</CTableHeaderCell>
                    <CTableHeaderCell>Symbol</CTableHeaderCell>
                    <CTableHeaderCell>Type</CTableHeaderCell>
                    <CTableHeaderCell>Volume</CTableHeaderCell>
                    <CTableHeaderCell>Open Price</CTableHeaderCell>
                    <CTableHeaderCell>Current Price</CTableHeaderCell>
                    <CTableHeaderCell>S/L</CTableHeaderCell>
                    <CTableHeaderCell>T/P</CTableHeaderCell>
                    <CTableHeaderCell>Profit</CTableHeaderCell>
                    <CTableHeaderCell>Open Time</CTableHeaderCell>
                  </CTableRow>
                </CTableHead>
                <CTableBody>
                  {positions.map((position) => (
                    <CTableRow key={position.ticket}>
                      <CTableDataCell>{position.ticket}</CTableDataCell>
                      <CTableDataCell className="fw-semibold">{position.symbol}</CTableDataCell>
                      <CTableDataCell>{getPositionTypeBadge(position.type)}</CTableDataCell>
                      <CTableDataCell>{formatVolume(position.volume)}</CTableDataCell>
                      <CTableDataCell>{position.price_open?.toFixed(5) || '-'}</CTableDataCell>
                      <CTableDataCell>{position.price_current?.toFixed(5) || '-'}</CTableDataCell>
                      <CTableDataCell>{position.sl?.toFixed(5) || '-'}</CTableDataCell>
                      <CTableDataCell>{position.tp?.toFixed(5) || '-'}</CTableDataCell>
                      <CTableDataCell className={`fw-semibold text-${getProfitColor(position.profit)}`}>
                        ${formatCurrency(position.profit)}
                      </CTableDataCell>
                      <CTableDataCell>
                        {position.time_create ? new Date(position.time_create).toLocaleString() : '-'}
                      </CTableDataCell>
                    </CTableRow>
                  ))}
                </CTableBody>
              </CTable>
            )}
          </CCardBody>
        </CCard>
      </CCol>

      <style>
        {`
          .rotating {
            animation: rotate 1s linear infinite;
          }
          @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}
      </style>
    </CRow>
  );
};

export default AccountDetail;
