/**
 * Positions Page - View all open positions across customers
 */
import React, { useEffect, useState } from 'react';
import {
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CRow,
  CSpinner,
  CTable,
  CTableBody,
  CTableDataCell,
  CTableHead,
  CTableHeaderCell,
  CTableRow,
  CAlert,
  CBadge,
  CFormInput,
  CFormSelect,
  CButton,
  CInputGroup,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilReload, cilSearch } from '@coreui/icons';
import { customersService } from '../services/customers';
import { accountsService } from '../services/accounts';

const Positions = () => {
  const [positions, setPositions] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      // Load customers
      const customersData = await customersService.getAll({ limit: 100 });
      setCustomers(customersData.items || []);

      // Load all positions
      await loadPositions();
    } catch (err) {
      setError('Failed to load data: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const loadPositions = async (customerId = null) => {
    try {
      setLoading(true);
      let allPositions = [];

      if (customerId) {
        // Load positions for specific customer
        const data = await customersService.getPositions(customerId, selectedSymbol || null);
        console.log('Positions data for customer:', customerId, data);
        
        // Extract positions from accounts
        if (data.accounts && Array.isArray(data.accounts)) {
          data.accounts.forEach(account => {
            if (account.positions && account.positions.length > 0) {
              allPositions.push(...account.positions.map(pos => ({
                ...pos,
                customer_name: data.customer_name,
                customer_id: data.customer_id,
              })));
            }
          });
        }
      } else {
        // Load positions for all customers
        const customersData = await customersService.getAll({ limit: 100 });
        const customers = customersData.items || [];
        console.log('Loading positions for customers:', customers.length);

        for (const customer of customers) {
          try {
            const data = await customersService.getPositions(customer.id, null);
            console.log(`Positions for customer ${customer.id}:`, data);
            
            // Extract positions from accounts
            if (data.accounts && Array.isArray(data.accounts)) {
              data.accounts.forEach(account => {
                if (account.positions && account.positions.length > 0) {
                  allPositions.push(...account.positions.map(pos => ({
                    ...pos,
                    customer_name: customer.name,
                    customer_id: customer.id,
                  })));
                }
              });
            }
          } catch (err) {
            console.error(`Failed to load positions for customer ${customer.id}:`, err);
          }
        }
      }

      console.log('All positions loaded:', allPositions);
      setPositions(allPositions);
    } catch (err) {
      setError('Failed to load positions: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleCustomerChange = (e) => {
    const customerId = e.target.value;
    setSelectedCustomer(customerId);
    if (customerId) {
      loadPositions(parseInt(customerId));
    } else {
      loadPositions();
    }
  };

  const getPositionTypeColor = (type) => {
    return type === 'BUY' ? 'success' : 'danger';
  };

  const getProfitColor = (profit) => {
    if (profit > 0) return 'success';
    if (profit < 0) return 'danger';
    return 'secondary';
  };

  // Calculate summary stats
  const totalVolume = positions.reduce((sum, pos) => sum + (pos.volume || 0), 0);
  const totalProfit = positions.reduce((sum, pos) => sum + (pos.profit || 0), 0);
  const buyPositions = positions.filter(pos => pos.action === 'BUY').length;
  const sellPositions = positions.filter(pos => pos.action === 'SELL').length;

  return (
    <>
      <CRow>
        <CCol>
          <h1 className="mb-4">Open Positions</h1>

          {error && (
            <CAlert color="danger" dismissible onClose={() => setError('')}>
              {error}
            </CAlert>
          )}

          {/* Summary Cards */}
          <CRow className="mb-4">
            <CCol sm={6} lg={3}>
              <CCard className="text-white bg-primary">
                <CCardBody className="pb-0 d-flex justify-content-between align-items-start">
                  <div>
                    <div className="fs-4 fw-semibold">{positions.length}</div>
                    <div>Total Positions</div>
                  </div>
                </CCardBody>
              </CCard>
            </CCol>
            <CCol sm={6} lg={3}>
              <CCard className="text-white bg-success">
                <CCardBody className="pb-0 d-flex justify-content-between align-items-start">
                  <div>
                    <div className="fs-4 fw-semibold">{buyPositions}</div>
                    <div>Buy Positions</div>
                  </div>
                </CCardBody>
              </CCard>
            </CCol>
            <CCol sm={6} lg={3}>
              <CCard className="text-white bg-danger">
                <CCardBody className="pb-0 d-flex justify-content-between align-items-start">
                  <div>
                    <div className="fs-4 fw-semibold">{sellPositions}</div>
                    <div>Sell Positions</div>
                  </div>
                </CCardBody>
              </CCard>
            </CCol>
            <CCol sm={6} lg={3}>
              <CCard className={`text-white bg-${getProfitColor(totalProfit)}`}>
                <CCardBody className="pb-0 d-flex justify-content-between align-items-start">
                  <div>
                    <div className="fs-4 fw-semibold">${totalProfit.toFixed(2)}</div>
                    <div>Total P/L</div>
                  </div>
                </CCardBody>
              </CCard>
            </CCol>
          </CRow>

          <CCard>
            <CCardHeader>
              <CRow className="align-items-center">
                <CCol>
                  <strong>Position List</strong>
                </CCol>
                <CCol xs="auto">
                  <CButton color="secondary" onClick={loadData}>
                    <CIcon icon={cilReload} className="me-2" />
                    Refresh
                  </CButton>
                </CCol>
              </CRow>
            </CCardHeader>

            <CCardBody>
              {/* Filters */}
              <CRow className="mb-3">
                <CCol md={6}>
                  <CFormSelect
                    value={selectedCustomer}
                    onChange={handleCustomerChange}
                  >
                    <option value="">All Customers</option>
                    {customers.map((customer) => (
                      <option key={customer.id} value={customer.id}>
                        {customer.name}
                      </option>
                    ))}
                  </CFormSelect>
                </CCol>
                <CCol md={6}>
                  <CFormInput
                    placeholder="Filter by symbol (e.g., EURUSD)"
                    value={selectedSymbol}
                    onChange={(e) => setSelectedSymbol(e.target.value)}
                  />
                </CCol>
              </CRow>

              {/* Table */}
              {loading ? (
                <div className="text-center py-5">
                  <CSpinner color="primary" />
                </div>
              ) : positions.length === 0 ? (
                <div className="text-center py-5 text-muted">
                  <p>No open positions found.</p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <CTable hover responsive>
                    <CTableHead>
                      <CTableRow>
                        <CTableHeaderCell>Position</CTableHeaderCell>
                        <CTableHeaderCell>Customer</CTableHeaderCell>
                        <CTableHeaderCell>Login</CTableHeaderCell>
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
                      {positions
                        .filter(pos => !selectedSymbol || pos.symbol?.toLowerCase().includes(selectedSymbol.toLowerCase()))
                        .map((pos, index) => (
                        <CTableRow key={index}>
                          <CTableDataCell>
                            <strong>#{pos.position || pos.ticket}</strong>
                          </CTableDataCell>
                          <CTableDataCell>{pos.customer_name || '-'}</CTableDataCell>
                          <CTableDataCell>{pos.login}</CTableDataCell>
                          <CTableDataCell>
                            <strong>{pos.symbol}</strong>
                          </CTableDataCell>
                          <CTableDataCell>
                            <CBadge color={getPositionTypeColor(pos.action)}>
                              {pos.action}
                            </CBadge>
                          </CTableDataCell>
                          <CTableDataCell>{pos.volume?.toFixed(2)}</CTableDataCell>
                          <CTableDataCell>{pos.price_open?.toFixed(5)}</CTableDataCell>
                          <CTableDataCell>{pos.price_current?.toFixed(5)}</CTableDataCell>
                          <CTableDataCell>{pos.price_sl?.toFixed(5) || '-'}</CTableDataCell>
                          <CTableDataCell>{pos.price_tp?.toFixed(5) || '-'}</CTableDataCell>
                          <CTableDataCell>
                            <strong className={`text-${getProfitColor(pos.profit)}`}>
                              ${pos.profit?.toFixed(2)}
                            </strong>
                          </CTableDataCell>
                          <CTableDataCell>
                            <small>
                              {pos.time_create ? new Date(pos.time_create * 1000).toLocaleString() : '-'}
                            </small>
                          </CTableDataCell>
                        </CTableRow>
                      ))}
                    </CTableBody>
                  </CTable>
                </div>
              )}
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>
    </>
  );
};

export default Positions;
