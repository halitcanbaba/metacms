import React, { useState, useEffect, useRef } from 'react';
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
  CNav,
  CNavItem,
  CNavLink,
  CTabContent,
  CTabPane,
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
  const [dealHistory, setDealHistory] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [loadingTradeHistory, setLoadingTradeHistory] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // disconnected, connecting, connected
  const [activeTab, setActiveTab] = useState('overview');
  
  // Use ref to store WebSocket instance for reliable cleanup
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

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

      // Fetch deal history for deposits/withdrawals
      const dealHistoryResponse = await api.get(`/api/accounts/${login}/deal-history`);
      setDealHistory(dealHistoryResponse.data || []);
    } catch (err) {
      console.error('Error fetching account data:', err);
      setError(err.response?.data?.detail || 'Failed to load account data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial data fetch
    fetchAccountData();

    // Setup WebSocket connection
    let shouldReconnect = true;

    const connectWebSocket = () => {
      // Close any existing connection before creating new one
      if (wsRef.current) {
        console.log(`Closing existing WebSocket before reconnect for account ${login}`);
        try {
          wsRef.current.close();
        } catch (e) {
          console.error('Error closing existing WebSocket:', e);
        }
      }

      setConnectionStatus('connecting');
      const websocket = new WebSocket(`ws://localhost:8000/ws/account/${login}`);
      wsRef.current = websocket;

      websocket.onopen = () => {
        console.log(`WebSocket connected for account ${login}`);
        setConnectionStatus('connected');
      };

      websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'account_update') {
          // Update realtime data only if changed
          if (data.realtime) {
            setRealtimeData(prevData => {
              const newData = {
                equity: data.realtime.equity,
                net_equity: data.realtime.net_equity,
                margin: data.realtime.margin,
                margin_free: data.realtime.margin_free,
                margin_level: data.realtime.margin_level,
                floating_profit: data.realtime.floating_profit,
              };
              
              // Only update if values actually changed
              if (!prevData || 
                  prevData.equity !== newData.equity ||
                  prevData.margin !== newData.margin ||
                  prevData.floating_profit !== newData.floating_profit) {
                return newData;
              }
              return prevData;
            });
          }

          // Update positions only if changed
          if (data.positions) {
            setPositions(prevPositions => {
              // Check if positions actually changed
              if (JSON.stringify(prevPositions) !== JSON.stringify(data.positions)) {
                return data.positions;
              }
              return prevPositions;
            });
          }
        }

        if (data.error) {
          console.error('WebSocket error:', data.error);
        }
      };

      websocket.onerror = (error) => {
        console.error(`WebSocket error for account ${login}:`, error);
        setConnectionStatus('disconnected');
      };

      websocket.onclose = (event) => {
        console.log(`WebSocket disconnected for account ${login}`, {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        });
        setConnectionStatus('disconnected');
        
        // Clean up ref if this is the current websocket
        if (wsRef.current === websocket) {
          wsRef.current = null;
        }
        
        // Only reconnect if we should and if the page is visible
        if (shouldReconnect && document.visibilityState === 'visible') {
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket();
          }, 2000);
        }
      };
    };

    connectWebSocket();

    // Cleanup on unmount or when login changes
    return () => {
      console.log(`Cleaning up WebSocket for account ${login}`);
      shouldReconnect = false; // Prevent reconnection
      
      // Clear any pending reconnect timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      // Close WebSocket connection
      if (wsRef.current) {
        const ws = wsRef.current;
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          console.log(`Forcefully closing WebSocket for account ${login}`);
          ws.close(1000, 'Component unmounting or login changed');
        }
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [login]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAccountData();
    setRefreshing(false);
  };

  const fetchTradeHistory = async () => {
    setLoadingTradeHistory(true);
    try {
      const response = await api.get(`/api/accounts/${login}/trade-history`);
      setTradeHistory(response.data || []);
    } catch (err) {
      console.error('Error fetching trade history:', err);
    } finally {
      setLoadingTradeHistory(false);
    }
  };

  // Fetch trade history when tab is switched
  useEffect(() => {
    if (activeTab === 'trade-history' && tradeHistory.length === 0) {
      fetchTradeHistory();
    }
  }, [activeTab]);

  const calculateNetPosition = () => {
    if (!positions || positions.length === 0) return { profit: 0, volume: 0 };
    
    const totalProfit = positions.reduce((sum, pos) => sum + (pos.profit || 0), 0);
    const totalVolume = positions.reduce((sum, pos) => sum + (pos.volume || 0), 0);
    
    return { profit: totalProfit, volume: totalVolume };
  };

  const calculateNetDeposit = () => {
    if (!dealHistory || dealHistory.length === 0) return 0;
    
    return dealHistory.reduce((sum, deal) => {
      if (deal.action === 'DEPOSIT') {
        return sum + deal.amount;
      } else if (deal.action === 'WITHDRAWAL') {
        return sum - deal.amount;
      }
      return sum;
    }, 0);
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
    // Support both number (0/1) and string ("buy"/"sell")
    const isBuy = type === 0 || type === '0' || 
                  (typeof type === 'string' && type.toLowerCase() === 'buy');
    
    return isBuy ? (
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
  const freeMargin = realtimeData?.margin_free || (equity - margin);
  const netDeposit = calculateNetDeposit();
  const overallPL = equity - netDeposit - credit;
  const marginLevel = margin > 0 ? ((equity / margin) * 100) : 0;

  return (
    <CRow>
      <CCol xs={12}>
        <CCard className="mb-4">
          <CCardHeader>
            <div className="d-flex justify-content-between align-items-center">
              <CNav variant="tabs" role="tablist">
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'overview'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('overview');
                    }}
                  >
                    Overview
                  </CNavLink>
                </CNavItem>
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'trade-history'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('trade-history');
                    }}
                  >
                    Trade History
                  </CNavLink>
                </CNavItem>
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'balance-history'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('balance-history');
                    }}
                  >
                    Balance History
                  </CNavLink>
                </CNavItem>
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'analysis'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('analysis');
                    }}
                  >
                    Analysis
                  </CNavLink>
                </CNavItem>
              </CNav>
              <div className="ms-3">
                <div className="text-medium-emphasis small">Account</div>
                <div className="fw-semibold">
                  #{accountInfo?.login} - {accountInfo?.name || accountInfo?.customer?.name || 'N/A'}
                </div>
              </div>
            </div>
          </CCardHeader>
        </CCard>
      </CCol>

      <CCol xs={12}>
        <CTabContent>
          <CTabPane visible={activeTab === 'overview'}>
            <CRow>
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
                      <CIcon icon={cilMoney} size="xl" className="me-3 text-info" />
                      <div>
                        <div className="text-medium-emphasis small">Net Deposit</div>
                        <div className="fs-5 fw-semibold">${formatCurrency(netDeposit)}</div>
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
                        <CBadge color={getProfitColor(overallPL)} style={{ fontSize: '1.5rem', padding: '0.5rem' }}>
                          P/L
                        </CBadge>
                      </div>
                      <div>
                        <div className="text-medium-emphasis small">Overall P/L</div>
                        <div className={`fs-5 fw-semibold text-${getProfitColor(overallPL)}`}>
                          ${formatCurrency(overallPL)}
                        </div>
                      </div>
                    </div>
                  </CCardBody>
                </CCard>
              </CCol>
            </CRow>

            <CRow>
              {/* Account Details */}
              <CCol xs={12} lg={6}>
                <CCard className="mb-4">
                  <CCardHeader>
                    <strong>Account Information</strong>
                    <CBadge 
                      color={connectionStatus === 'connected' ? 'success' : connectionStatus === 'connecting' ? 'warning' : 'secondary'}
                      className="ms-2"
                      style={{ fontSize: '0.6rem', verticalAlign: 'middle' }}
                    >
                      {connectionStatus === 'connected' ? '● LIVE' : connectionStatus === 'connecting' ? '● CONNECTING' : '● OFFLINE'}
                    </CBadge>
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
                          <CTableDataCell>{accountInfo?.name || accountInfo?.customer?.name || '-'}</CTableDataCell>
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
            </CRow>

            <CRow>
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
            </CRow>

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
          </CTabPane>

          {/* Trade History Tab */}
          <CTabPane visible={activeTab === 'trade-history'}>
            <CRow>
              <CCol xs={12}>
                <CCard>
                  <CCardHeader>
                    <strong>Closed Trades</strong>
                    <CButton 
                      size="sm" 
                      color="primary" 
                      className="float-end"
                      onClick={fetchTradeHistory}
                      disabled={loadingTradeHistory}
                    >
                      {loadingTradeHistory ? <CSpinner size="sm" /> : <CIcon icon={cilReload} />}
                      {' '}Refresh
                    </CButton>
                  </CCardHeader>
                  <CCardBody>
                    {loadingTradeHistory ? (
                      <div className="text-center py-4">
                        <CSpinner color="primary" />
                        <div className="mt-2 text-muted">Loading trade history...</div>
                      </div>
                    ) : tradeHistory.length === 0 ? (
                      <div className="text-center text-medium-emphasis py-4">
                        No closed trades found
                      </div>
                    ) : (
                      <CTable striped hover responsive>
                        <CTableHead>
                          <CTableRow>
                            <CTableHeaderCell>Deal ID</CTableHeaderCell>
                            <CTableHeaderCell>Symbol</CTableHeaderCell>
                            <CTableHeaderCell>Type</CTableHeaderCell>
                            <CTableHeaderCell>Close Date/Time</CTableHeaderCell>
                            <CTableHeaderCell>Volume</CTableHeaderCell>
                            <CTableHeaderCell>Price</CTableHeaderCell>
                            <CTableHeaderCell>Commission</CTableHeaderCell>
                            <CTableHeaderCell>Swap</CTableHeaderCell>
                            <CTableHeaderCell>Profit</CTableHeaderCell>
                          </CTableRow>
                        </CTableHead>
                        <CTableBody>
                          {tradeHistory.map((trade) => {
                            return (
                              <CTableRow key={trade.deal_id}>
                                <CTableDataCell>{trade.deal_id}</CTableDataCell>
                                <CTableDataCell className="fw-semibold">{trade.symbol}</CTableDataCell>
                                <CTableDataCell>
                                  <CBadge color={trade.action === 'BUY' ? 'success' : 'danger'}>
                                    {trade.action}
                                  </CBadge>
                                </CTableDataCell>
                                <CTableDataCell>{trade.datetime || '-'}</CTableDataCell>
                                <CTableDataCell>{formatVolume(trade.volume)}</CTableDataCell>
                                <CTableDataCell>{trade.price?.toFixed(5) || '-'}</CTableDataCell>
                                <CTableDataCell className={`text-${getProfitColor(trade.commission)}`}>
                                  ${formatCurrency(trade.commission)}
                                </CTableDataCell>
                                <CTableDataCell className={`text-${getProfitColor(trade.swap)}`}>
                                  ${formatCurrency(trade.swap)}
                                </CTableDataCell>
                                <CTableDataCell className={`fw-semibold text-${getProfitColor(trade.profit)}`}>
                                  ${formatCurrency(trade.profit)}
                                </CTableDataCell>
                              </CTableRow>
                            );
                          })}
                        </CTableBody>
                      </CTable>
                    )}
                  </CCardBody>
                </CCard>
              </CCol>
            </CRow>
          </CTabPane>

          {/* Balance History Tab */}
          <CTabPane visible={activeTab === 'balance-history'}>
            <CRow>
              <CCol xs={12}>
                <CCard>
                  <CCardHeader>
                    <strong>Balance Operations History</strong>
                  </CCardHeader>
                  <CCardBody>
                    {dealHistory.length === 0 ? (
                      <div className="text-center text-medium-emphasis py-4">
                        No balance operations found
                      </div>
                    ) : (
                      <CTable striped hover responsive>
                        <CTableHead>
                          <CTableRow>
                            <CTableHeaderCell>Date/Time</CTableHeaderCell>
                            <CTableHeaderCell>Type</CTableHeaderCell>
                            <CTableHeaderCell>Amount</CTableHeaderCell>
                            <CTableHeaderCell>Balance After</CTableHeaderCell>
                            <CTableHeaderCell>Comment</CTableHeaderCell>
                          </CTableRow>
                        </CTableHead>
                        <CTableBody>
                          {dealHistory.map((deal) => {
                            // Determine badge color based on action type
                            let badgeColor = 'secondary';
                            if (deal.action === 'DEPOSIT') badgeColor = 'success';
                            else if (deal.action === 'WITHDRAWAL') badgeColor = 'danger';
                            else if (deal.action === 'CREDIT') badgeColor = 'info';
                            else if (deal.action === 'CREDIT_OUT') badgeColor = 'warning';
                            
                            return (
                              <CTableRow key={deal.deal_id}>
                                <CTableDataCell>{deal.datetime_str || '-'}</CTableDataCell>
                                <CTableDataCell>
                                  <CBadge color={badgeColor}>
                                    {deal.action}
                                  </CBadge>
                                </CTableDataCell>
                                <CTableDataCell className={`fw-semibold text-${getProfitColor(deal.amount)}`}>
                                  ${formatCurrency(Math.abs(deal.amount))}
                                </CTableDataCell>
                                <CTableDataCell className="fw-semibold">
                                  ${formatCurrency(deal.balance_after)}
                                </CTableDataCell>
                                <CTableDataCell className="text-muted">
                                  {deal.comment || '-'}
                                </CTableDataCell>
                              </CTableRow>
                            );
                          })}
                        </CTableBody>
                      </CTable>
                    )}
                  </CCardBody>
                </CCard>
              </CCol>
            </CRow>
          </CTabPane>

          {/* Analysis Tab */}
          <CTabPane visible={activeTab === 'analysis'}>
            <CCard>
              <CCardBody>
                <h5>Analysis</h5>
                <p className="text-muted">Coming soon...</p>
              </CCardBody>
            </CCard>
          </CTabPane>
        </CTabContent>
      </CCol>

      {/* Smooth transitions for live updates */}
      <style>{`
        .card-body {
          transition: all 0.15s ease-in-out;
        }
        
        .fs-5, .fw-semibold {
          transition: color 0.15s ease-in-out;
        }
        
        @keyframes rotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        
        .rotating {
          animation: rotate 1s linear infinite;
        }
      `}</style>
    </CRow>
  );
};

export default AccountDetail;
