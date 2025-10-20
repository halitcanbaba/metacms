/**
 * Balance Operations Page - Deposit, Withdrawal, Credit
 */
import React, { useEffect, useState } from 'react';
import api from '../services/api';
import {
  CButton,
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CForm,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CFormTextarea,
  CNav,
  CNavItem,
  CNavLink,
  CRow,
  CAlert,
  CTabContent,
  CTabPane,
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
import { cilCash, cilArrowTop, cilArrowBottom, cilHistory } from '@coreui/icons';
import { balanceService } from '../services/balance';
import { accountsService } from '../services/accounts';

const Balance = () => {
  const [activeTab, setActiveTab] = useState('deposit');
  const [accounts, setAccounts] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Account info state
  const [selectedAccountInfo, setSelectedAccountInfo] = useState(null);
  const [accountHistory, setAccountHistory] = useState([]);
  const [accountPositions, setAccountPositions] = useState([]);
  const [loadingAccountInfo, setLoadingAccountInfo] = useState(false);
  const [accountError, setAccountError] = useState('');

  // Form state
  const [formData, setFormData] = useState({
    login: '',
    amount: '',
    comment: '',
  });

  useEffect(() => {
    loadAccounts();
    loadHistory();
  }, []);

  const loadAccounts = async () => {
    try {
      const data = await accountsService.getAll({ limit: 100 });
      setAccounts(data.items || []);
    } catch (err) {
      console.error('Failed to load accounts:', err);
    }
  };

  const loadHistory = async () => {
    try {
      setLoading(true);
      const data = await balanceService.getHistory({ limit: 50 });
      setHistory(data.items || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    
    // When login changes, debounce account info fetch
    if (name === 'login') {
      if (!value) {
        setSelectedAccountInfo(null);
        setAccountHistory([]);
        setAccountPositions([]);
        setAccountError('');
      } else if (value.length >= 6) {
        // Only fetch if login has at least 6 digits
        // Debounce: wait 500ms after user stops typing
        if (window.accountInfoTimeout) {
          clearTimeout(window.accountInfoTimeout);
        }
        window.accountInfoTimeout = setTimeout(() => {
          loadAccountInfo(value);
        }, 500);
      }
    }
  };

  const loadAccountInfo = async (login) => {
    if (!login) {
      setSelectedAccountInfo(null);
      setAccountHistory([]);
      setAccountPositions([]);
      setAccountError('');
      return;
    }
    
    try {
      setLoadingAccountInfo(true);
      setSelectedAccountInfo(null);
      setAccountHistory([]);
      setAccountPositions([]);
      setAccountError('');
      
      // Get date range: 30 days ago to tomorrow (to include today's deals)
      const tomorrow = new Date(Date.now() + 24*60*60*1000);
      const toDate = tomorrow.toISOString().split('T')[0];
      const fromDate = new Date(Date.now() - 30*24*60*60*1000).toISOString().split('T')[0];
      
      // Fetch realtime account info
      const realtimeResponse = await api.get(`/api/accounts/realtime?login=${login}`);
      
      if (!realtimeResponse.data || realtimeResponse.data.length === 0) {
        throw new Error('Account not found');
      }
      
      // Fetch deal history
      let dealsData = [];
      try {
        const dealsResponse = await api.get(`/api/accounts/history/deals?login=${login}&from_date=${fromDate}&to_date=${toDate}`);
        dealsData = dealsResponse.data || [];
      } catch (err) {
        console.warn('Failed to fetch deal history:', err);
      }
      
      // Fetch open positions
      let positionsData = [];
      try {
        const positionsResponse = await api.get(`/api/accounts/positions/account/${login}`);
        positionsData = positionsResponse.data || [];
      } catch (err) {
        console.warn('Failed to fetch positions:', err);
      }
      
      setSelectedAccountInfo(realtimeResponse.data[0]);
      setAccountHistory(dealsData);
      setAccountPositions(positionsData);
      
      console.log('Account info loaded:', { 
        login, 
        account: realtimeResponse.data[0], 
        deals: dealsData.length,
        positions: positionsData.length
      });
    } catch (err) {
      console.error('Failed to load account info:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Account not found';
      setAccountError(errorMsg);
      setSelectedAccountInfo(null);
      setAccountHistory([]);
      setAccountPositions([]);
    } finally {
      setLoadingAccountInfo(false);
    }
  };

  const handleSubmit = async (e, operationType) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      const amount = parseFloat(formData.amount);
      if (isNaN(amount) || amount <= 0) {
        setError('Please enter a valid amount');
        return;
      }

      switch (operationType) {
        case 'deposit':
          await balanceService.deposit(
            parseInt(formData.login),
            amount,
            formData.comment || 'Deposit'
          );
          setSuccess('Deposit successful!');
          break;

        case 'withdrawal':
          await balanceService.withdrawal(
            parseInt(formData.login),
            amount,
            formData.comment || 'Withdrawal'
          );
          setSuccess('Withdrawal successful!');
          break;

        case 'credit':
          const creditAmount = parseFloat(formData.amount);
          await balanceService.createCredit(
            parseInt(formData.login),
            creditAmount,
            formData.comment || 'Credit operation'
          );
          setSuccess(`Credit ${creditAmount > 0 ? 'in' : 'out'} successful!`);
          break;

        default:
          setError('Invalid operation type');
          return;
      }

      // Reset form
      setFormData({ login: '', amount: '', comment: '' });
      loadHistory();
      loadAccounts();
    } catch (err) {
      setError(err.response?.data?.detail || 'Operation failed');
    }
  };

  const getOperationColor = (type) => {
    switch (type?.toLowerCase()) {
      case 'deposit':
      case 'credit_in':
        return 'success';
      case 'withdrawal':
      case 'credit_out':
        return 'danger';
      default:
        return 'secondary';
    }
  };

  const getOperationIcon = (type) => {
    switch (type?.toLowerCase()) {
      case 'deposit':
      case 'credit_in':
        return cilArrowTop;
      case 'withdrawal':
      case 'credit_out':
        return cilArrowBottom;
      default:
        return cilCash;
    }
  };

  return (
    <>
      <CRow>
        <CCol>
          <h1 className="mb-4">Balance Operations</h1>

          {error && (
            <CAlert color="danger" dismissible onClose={() => setError('')}>
              {error}
            </CAlert>
          )}

          {success && (
            <CAlert color="success" dismissible onClose={() => setSuccess('')}>
              {success}
            </CAlert>
          )}

          <CCard className="mb-4">
            <CCardHeader>
              <CNav variant="tabs" role="tablist">
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'deposit'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('deposit');
                    }}
                  >
                    <CIcon icon={cilArrowTop} className="me-2" />
                    Deposit
                  </CNavLink>
                </CNavItem>
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'withdrawal'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('withdrawal');
                    }}
                  >
                    <CIcon icon={cilArrowBottom} className="me-2" />
                    Withdrawal
                  </CNavLink>
                </CNavItem>
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'credit'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('credit');
                    }}
                  >
                    <CIcon icon={cilCash} className="me-2" />
                    Credit
                  </CNavLink>
                </CNavItem>
                <CNavItem>
                  <CNavLink
                    href="#"
                    active={activeTab === 'history'}
                    onClick={(e) => {
                      e.preventDefault();
                      setActiveTab('history');
                      loadHistory();
                    }}
                  >
                    <CIcon icon={cilHistory} className="me-2" />
                    History
                  </CNavLink>
                </CNavItem>
              </CNav>
            </CCardHeader>

            <CCardBody>
              <CTabContent>
                {/* Deposit Tab */}
                <CTabPane visible={activeTab === 'deposit'}>
                  <CRow>
                    <CCol md={selectedAccountInfo ? 7 : 12}>
                      <CForm onSubmit={(e) => handleSubmit(e, 'deposit')}>
                        <CRow className="mb-3">
                          <CCol md={12}>
                            <CFormLabel>MT5 Account Login *</CFormLabel>
                            <CFormInput
                              type="number"
                              name="login"
                              value={formData.login}
                              onChange={handleInputChange}
                              placeholder="Enter account login number"
                              required
                            />
                            <small className="text-muted">
                              Type account login to see details
                            </small>
                          </CCol>
                        </CRow>
                        
                        <CRow className="mb-3">
                          <CCol md={6}>
                            <CFormLabel>Amount *</CFormLabel>
                            <CFormInput
                              type="number"
                              name="amount"
                              step="0.01"
                              min="0.01"
                              value={formData.amount}
                              onChange={handleInputChange}
                              placeholder="0.00"
                              required
                            />
                          </CCol>
                          <CCol md={6}>
                            <CFormLabel>Comment</CFormLabel>
                            <CFormInput
                              name="comment"
                              value={formData.comment}
                              onChange={handleInputChange}
                              placeholder="Optional comment..."
                            />
                          </CCol>
                        </CRow>
                        
                        <CButton 
                          type="submit" 
                          color="success" 
                          disabled={!formData.login || !!accountError || !selectedAccountInfo || loading}
                        >
                          <CIcon icon={cilArrowTop} className="me-2" />
                          Deposit
                        </CButton>
                      </CForm>
                    </CCol>
                    
                    {/* Account Info Sidebar */}
                    {(selectedAccountInfo || accountError) && (
                      <CCol md={5}>
                        <CCard className="bg-light">
                          <CCardHeader className="fw-bold">
                            Account Information
                          </CCardHeader>
                          <CCardBody>
                            {loadingAccountInfo ? (
                              <div className="text-center">
                                <CSpinner size="sm" />
                              </div>
                            ) : accountError ? (
                              <CAlert color="danger" className="mb-0">
                                <strong>Error:</strong> {accountError}
                              </CAlert>
                            ) : (
                              <>
                                <table className="table table-sm table-borderless mb-3">
                                  <tbody>
                                    <tr>
                                      <td className="text-muted">Name:</td>
                                      <td className="fw-bold">{selectedAccountInfo.name}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Login:</td>
                                      <td className="fw-bold">{selectedAccountInfo.login}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Group:</td>
                                      <td>{selectedAccountInfo.group}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Balance:</td>
                                      <td className="fw-bold text-primary">
                                        ${selectedAccountInfo.balance?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Credit:</td>
                                      <td>${selectedAccountInfo.credit?.toFixed(2)}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Equity:</td>
                                      <td className="fw-bold text-success">
                                        ${selectedAccountInfo.equity?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Net Equity:</td>
                                      <td className="fw-bold">
                                        ${selectedAccountInfo.net_equity?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Floating P/L:</td>
                                      <td className={selectedAccountInfo.floating_profit >= 0 ? 'text-success' : 'text-danger'}>
                                        ${selectedAccountInfo.floating_profit?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Margin:</td>
                                      <td>${selectedAccountInfo.margin?.toFixed(2)}</td>
                                    </tr>
                                  </tbody>
                                </table>
                                
                                <hr />
                                
                                <div className="mb-2">
                                  <strong className="text-muted">Recent History (30 days)</strong>
                                </div>
                                {accountHistory.length > 0 ? (
                                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                    {accountHistory
                                      .sort((a, b) => b.timestamp - a.timestamp)
                                      .slice(0, 10)
                                      .map((deal) => (
                                      <div key={deal.deal_id} className="border-bottom py-2">
                                        <div className="d-flex justify-content-between">
                                          <small>
                                            <CBadge color={deal.action === 'DEPOSIT' ? 'success' : deal.action === 'WITHDRAWAL' ? 'danger' : 'info'}>
                                              {deal.action}
                                            </CBadge>
                                          </small>
                                          <small className={deal.amount >= 0 ? 'text-success' : 'text-danger'}>
                                            ${deal.amount?.toFixed(2)}
                                          </small>
                                        </div>
                                        <small className="text-muted d-block">
                                          {deal.datetime_str}
                                          {deal.comment && <span className="text-info"> - {deal.comment}</span>}
                                        </small>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <small className="text-muted">No recent transactions</small>
                                )}
                                
                                <hr />
                                
                                <div className="mb-2">
                                  <strong className="text-muted">Open Positions</strong>
                                </div>
                                {accountPositions.length > 0 ? (
                                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                    {accountPositions.map((pos) => (
                                      <div key={pos.ticket} className="border-bottom py-2">
                                        <div className="d-flex justify-content-between align-items-center">
                                          <div>
                                            <strong>{pos.symbol}</strong>
                                            <CBadge 
                                              color={pos.type === 'BUY' ? 'primary' : 'warning'} 
                                              className="ms-2"
                                            >
                                              {pos.type}
                                            </CBadge>
                                            <small className="text-muted d-block">
                                              Vol: {pos.volume?.toFixed(2)} | Entry: ${pos.price_open?.toFixed(5)}
                                            </small>
                                          </div>
                                          <div className="text-end">
                                            <small className={pos.profit >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold'}>
                                              ${pos.profit?.toFixed(2)}
                                            </small>
                                            <small className="text-muted d-block">
                                              @ ${pos.price_current?.toFixed(5)}
                                            </small>
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <small className="text-muted">No open positions</small>
                                )}
                              </>
                            )}
                          </CCardBody>
                        </CCard>
                      </CCol>
                    )}
                  </CRow>
                </CTabPane>

                {/* Withdrawal Tab */}
                <CTabPane visible={activeTab === 'withdrawal'}>
                  <CRow className="mb-3">
                    <CCol md={(selectedAccountInfo || accountError) ? 7 : 12}>
                      <CForm onSubmit={(e) => handleSubmit(e, 'withdrawal')}>
                        <CRow className="mb-3">
                          <CCol md={12}>
                            <CFormLabel>MT5 Account Login *</CFormLabel>
                            <CFormInput
                              type="number"
                              name="login"
                              value={formData.login}
                              onChange={handleInputChange}
                              placeholder="Enter account login number"
                              required
                            />
                          </CCol>
                        </CRow>
                        <CRow className="mb-3">
                          <CCol md={6}>
                            <CFormLabel>Amount *</CFormLabel>
                            <CFormInput
                              type="number"
                              name="amount"
                              step="0.01"
                              min="0.01"
                              value={formData.amount}
                              onChange={handleInputChange}
                              placeholder="0.00"
                              required
                            />
                          </CCol>
                          <CCol md={6}>
                            <CFormLabel>Comment</CFormLabel>
                            <CFormInput
                              name="comment"
                              value={formData.comment}
                              onChange={handleInputChange}
                              placeholder="Optional comment..."
                            />
                          </CCol>
                        </CRow>
                        <CButton 
                          type="submit" 
                          color="danger" 
                          disabled={!formData.login || !!accountError || !selectedAccountInfo || loading}
                        >
                          <CIcon icon={cilArrowBottom} className="me-2" />
                          Withdraw
                        </CButton>
                      </CForm>
                    </CCol>
                    
                    {/* Account Info Sidebar */}
                    {(selectedAccountInfo || accountError) && (
                      <CCol md={5}>
                        <CCard className="bg-light">
                          <CCardHeader className="fw-bold">
                            Account Information
                          </CCardHeader>
                          <CCardBody>
                            {loadingAccountInfo ? (
                              <div className="text-center">
                                <CSpinner size="sm" />
                              </div>
                            ) : accountError ? (
                              <CAlert color="danger" className="mb-0">
                                <strong>Error:</strong> {accountError}
                              </CAlert>
                            ) : (
                              <>
                                <table className="table table-sm table-borderless mb-3">
                                  <tbody>
                                    <tr>
                                      <td className="text-muted">Name:</td>
                                      <td className="fw-bold">{selectedAccountInfo.name}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Login:</td>
                                      <td className="fw-bold">{selectedAccountInfo.login}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Group:</td>
                                      <td>{selectedAccountInfo.group}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Balance:</td>
                                      <td className="fw-bold text-primary">
                                        ${selectedAccountInfo.balance?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Credit:</td>
                                      <td>${selectedAccountInfo.credit?.toFixed(2)}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Equity:</td>
                                      <td className="fw-bold text-success">
                                        ${selectedAccountInfo.equity?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Net Equity:</td>
                                      <td className="fw-bold">
                                        ${selectedAccountInfo.net_equity?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Floating P/L:</td>
                                      <td className={selectedAccountInfo.floating_profit >= 0 ? 'text-success' : 'text-danger'}>
                                        ${selectedAccountInfo.floating_profit?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Margin:</td>
                                      <td>${selectedAccountInfo.margin?.toFixed(2)}</td>
                                    </tr>
                                  </tbody>
                                </table>
                                
                                <hr />
                                
                                <div className="mb-2">
                                  <strong className="text-muted">Recent History (30 days)</strong>
                                </div>
                                {accountHistory.length > 0 ? (
                                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                    {accountHistory
                                      .sort((a, b) => b.timestamp - a.timestamp)
                                      .slice(0, 10)
                                      .map((deal) => (
                                      <div key={deal.deal_id} className="border-bottom py-2">
                                        <div className="d-flex justify-content-between">
                                          <small>
                                            <CBadge color={deal.action === 'DEPOSIT' ? 'success' : deal.action === 'WITHDRAWAL' ? 'danger' : 'info'}>
                                              {deal.action}
                                            </CBadge>
                                          </small>
                                          <small className={deal.amount >= 0 ? 'text-success' : 'text-danger'}>
                                            ${deal.amount?.toFixed(2)}
                                          </small>
                                        </div>
                                        <small className="text-muted d-block">
                                          {deal.datetime_str}
                                          {deal.comment && <span className="text-info"> - {deal.comment}</span>}
                                        </small>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <small className="text-muted">No recent transactions</small>
                                )}
                                
                                <hr />
                                
                                <div className="mb-2">
                                  <strong className="text-muted">Open Positions</strong>
                                </div>
                                {accountPositions.length > 0 ? (
                                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                    {accountPositions.map((pos) => (
                                      <div key={pos.ticket} className="border-bottom py-2">
                                        <div className="d-flex justify-content-between align-items-center">
                                          <div>
                                            <strong>{pos.symbol}</strong>
                                            <CBadge 
                                              color={pos.type === 'BUY' ? 'primary' : 'warning'} 
                                              className="ms-2"
                                            >
                                              {pos.type}
                                            </CBadge>
                                            <small className="text-muted d-block">
                                              Vol: {pos.volume?.toFixed(2)} | Entry: ${pos.price_open?.toFixed(5)}
                                            </small>
                                          </div>
                                          <div className="text-end">
                                            <small className={pos.profit >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold'}>
                                              ${pos.profit?.toFixed(2)}
                                            </small>
                                            <small className="text-muted d-block">
                                              @ ${pos.price_current?.toFixed(5)}
                                            </small>
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <small className="text-muted">No open positions</small>
                                )}
                              </>
                            )}
                          </CCardBody>
                        </CCard>
                      </CCol>
                    )}
                  </CRow>
                </CTabPane>

                {/* Credit Tab */}
                <CTabPane visible={activeTab === 'credit'}>
                  <CRow className="mb-3">
                    <CCol md={(selectedAccountInfo || accountError) ? 7 : 12}>
                      <CForm onSubmit={(e) => handleSubmit(e, 'credit')}>
                        <CRow className="mb-3">
                          <CCol md={12}>
                            <CFormLabel>MT5 Account Login *</CFormLabel>
                            <CFormInput
                              type="number"
                              name="login"
                              value={formData.login}
                              onChange={handleInputChange}
                              placeholder="Enter account login number"
                              required
                            />
                          </CCol>
                        </CRow>
                        <CRow className="mb-3">
                          <CCol md={6}>
                            <CFormLabel>Amount * (+ or -)</CFormLabel>
                            <CFormInput
                              type="number"
                              name="amount"
                              step="0.01"
                              value={formData.amount}
                              onChange={handleInputChange}
                              placeholder="Positive = Credit In, Negative = Credit Out"
                              required
                            />
                          </CCol>
                          <CCol md={6}>
                            <CFormLabel>Comment</CFormLabel>
                            <CFormInput
                              name="comment"
                              value={formData.comment}
                              onChange={handleInputChange}
                              placeholder="Optional comment..."
                            />
                          </CCol>
                        </CRow>
                        <CButton 
                          type="submit" 
                          color="primary" 
                          disabled={!formData.login || !!accountError || !selectedAccountInfo || loading}
                        >
                          <CIcon icon={cilCash} className="me-2" />
                          Apply Credit
                        </CButton>
                      </CForm>
                    </CCol>
                    
                    {/* Account Info Sidebar */}
                    {(selectedAccountInfo || accountError) && (
                      <CCol md={5}>
                        <CCard className="bg-light">
                          <CCardHeader className="fw-bold">
                            Account Information
                          </CCardHeader>
                          <CCardBody>
                            {loadingAccountInfo ? (
                              <div className="text-center">
                                <CSpinner size="sm" />
                              </div>
                            ) : accountError ? (
                              <CAlert color="danger" className="mb-0">
                                <strong>Error:</strong> {accountError}
                              </CAlert>
                            ) : (
                              <>
                                <table className="table table-sm table-borderless mb-3">
                                  <tbody>
                                    <tr>
                                      <td className="text-muted">Name:</td>
                                      <td className="fw-bold">{selectedAccountInfo.name}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Login:</td>
                                      <td className="fw-bold">{selectedAccountInfo.login}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Group:</td>
                                      <td>{selectedAccountInfo.group}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Balance:</td>
                                      <td className="fw-bold text-primary">
                                        ${selectedAccountInfo.balance?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Credit:</td>
                                      <td>${selectedAccountInfo.credit?.toFixed(2)}</td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Equity:</td>
                                      <td className="fw-bold text-success">
                                        ${selectedAccountInfo.equity?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Net Equity:</td>
                                      <td className="fw-bold">
                                        ${selectedAccountInfo.net_equity?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Floating P/L:</td>
                                      <td className={selectedAccountInfo.floating_profit >= 0 ? 'text-success' : 'text-danger'}>
                                        ${selectedAccountInfo.floating_profit?.toFixed(2)}
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="text-muted">Margin:</td>
                                      <td>${selectedAccountInfo.margin?.toFixed(2)}</td>
                                    </tr>
                                  </tbody>
                                </table>
                                
                                <hr />
                                
                                <div className="mb-2">
                                  <strong className="text-muted">Recent History (30 days)</strong>
                                </div>
                                {accountHistory.length > 0 ? (
                                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                    {accountHistory
                                      .sort((a, b) => b.timestamp - a.timestamp)
                                      .slice(0, 10)
                                      .map((deal) => (
                                      <div key={deal.deal_id} className="border-bottom py-2">
                                        <div className="d-flex justify-content-between">
                                          <small>
                                            <CBadge color={deal.action === 'DEPOSIT' ? 'success' : deal.action === 'WITHDRAWAL' ? 'danger' : 'info'}>
                                              {deal.action}
                                            </CBadge>
                                          </small>
                                          <small className={deal.amount >= 0 ? 'text-success' : 'text-danger'}>
                                            ${deal.amount?.toFixed(2)}
                                          </small>
                                        </div>
                                        <small className="text-muted d-block">
                                          {deal.datetime_str}
                                          {deal.comment && <span className="text-info"> - {deal.comment}</span>}
                                        </small>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <small className="text-muted">No recent transactions</small>
                                )}
                                
                                <hr />
                                
                                <div className="mb-2">
                                  <strong className="text-muted">Open Positions</strong>
                                </div>
                                {accountPositions.length > 0 ? (
                                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                    {accountPositions.map((pos) => (
                                      <div key={pos.ticket} className="border-bottom py-2">
                                        <div className="d-flex justify-content-between align-items-center">
                                          <div>
                                            <strong>{pos.symbol}</strong>
                                            <CBadge 
                                              color={pos.type === 'BUY' ? 'primary' : 'warning'} 
                                              className="ms-2"
                                            >
                                              {pos.type}
                                            </CBadge>
                                            <small className="text-muted d-block">
                                              Vol: {pos.volume?.toFixed(2)} | Entry: ${pos.price_open?.toFixed(5)}
                                            </small>
                                          </div>
                                          <div className="text-end">
                                            <small className={pos.profit >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold'}>
                                              ${pos.profit?.toFixed(2)}
                                            </small>
                                            <small className="text-muted d-block">
                                              @ ${pos.price_current?.toFixed(5)}
                                            </small>
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <small className="text-muted">No open positions</small>
                                )}
                              </>
                            )}
                          </CCardBody>
                        </CCard>
                      </CCol>
                    )}
                  </CRow>
                </CTabPane>

                {/* History Tab */}
                <CTabPane visible={activeTab === 'history'}>
                  {loading ? (
                    <div className="text-center py-5">
                      <CSpinner color="primary" />
                    </div>
                  ) : history.length === 0 ? (
                    <div className="text-center py-5 text-muted">
                      <p>No operations yet.</p>
                    </div>
                  ) : (
                    <CTable hover responsive>
                      <CTableHead>
                        <CTableRow>
                          <CTableHeaderCell>ID</CTableHeaderCell>
                          <CTableHeaderCell>Login</CTableHeaderCell>
                          <CTableHeaderCell>Type</CTableHeaderCell>
                          <CTableHeaderCell>Amount</CTableHeaderCell>
                          <CTableHeaderCell>Comment</CTableHeaderCell>
                          <CTableHeaderCell>Status</CTableHeaderCell>
                          <CTableHeaderCell>Date</CTableHeaderCell>
                        </CTableRow>
                      </CTableHead>
                      <CTableBody>
                        {history.map((op) => (
                          <CTableRow key={op.id}>
                            <CTableDataCell>{op.id}</CTableDataCell>
                            <CTableDataCell>
                              <strong>{op.login}</strong>
                            </CTableDataCell>
                            <CTableDataCell>
                              <CBadge color={getOperationColor(op.type)}>
                                <CIcon icon={getOperationIcon(op.type)} className="me-1" />
                                {op.type}
                              </CBadge>
                            </CTableDataCell>
                            <CTableDataCell>
                              <strong>${op.amount?.toFixed(2)}</strong>
                            </CTableDataCell>
                            <CTableDataCell>{op.comment || '-'}</CTableDataCell>
                            <CTableDataCell>
                              <CBadge color={op.status === 'completed' ? 'success' : 'warning'}>
                                {op.status}
                              </CBadge>
                            </CTableDataCell>
                            <CTableDataCell>
                              {new Date(op.created_at).toLocaleString()}
                            </CTableDataCell>
                          </CTableRow>
                        ))}
                      </CTableBody>
                    </CTable>
                  )}
                </CTabPane>
              </CTabContent>
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>
    </>
  );
};

export default Balance;
