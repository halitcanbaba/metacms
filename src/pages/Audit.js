/**
 * Audit Logs Page - View system activity logs
 */
import React, { useEffect, useState, useCallback } from 'react';
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
  CFormSelect,
  CButton,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilReload, cilFilter } from '@coreui/icons';
import api from '../services/api';

const Audit = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({
    action: '',
    entity_type: '',
    search: '',
  });

  const loadLogs = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      
      const params = new URLSearchParams();
      if (filters.action) params.append('action', filters.action);
      if (filters.entity_type) params.append('entity_type', filters.entity_type);
      params.append('limit', '100');

      const response = await api.get(`/api/audit?${params.toString()}`);
      setLogs(response.data.items || []);
    } catch (err) {
      setError('Failed to load audit logs: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, [filters.action, filters.entity_type]); // Dependencies are the filter values used in the API call

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const getActionColor = (action) => {
    switch (action?.toLowerCase()) {
      case 'create':
        return 'success';
      case 'update':
        return 'info';
      case 'delete':
        return 'danger';
      case 'login':
        return 'primary';
      default:
        return 'secondary';
    }
  };

  const getEntityIcon = (entityType) => {
    switch (entityType?.toLowerCase()) {
      case 'customer':
        return '👤';
      case 'account':
        return '💰';
      case 'balance_operation':
        return '💳';
      case 'user':
        return '👨‍💼';
      default:
        return '📝';
    }
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <>
      <CRow>
        <CCol>
          <h1 className="mb-4">Audit Logs</h1>

          {error && (
            <CAlert color="danger" dismissible onClose={() => setError('')}>
              {error}
            </CAlert>
          )}

          <CCard>
            <CCardHeader>
              <CRow className="align-items-center">
                <CCol>
                  <strong>System Activity Logs</strong>
                </CCol>
                <CCol xs="auto">
                  <CButton color="secondary" onClick={loadLogs}>
                    <CIcon icon={cilReload} className="me-2" />
                    Refresh
                  </CButton>
                </CCol>
              </CRow>
            </CCardHeader>

            <CCardBody>
              {/* Filters */}
              <CRow className="mb-3">
                <CCol md={4}>
                  <CFormSelect
                    name="action"
                    value={filters.action}
                    onChange={handleFilterChange}
                  >
                    <option value="">All Actions</option>
                    <option value="CREATE">Create</option>
                    <option value="UPDATE">Update</option>
                    <option value="DELETE">Delete</option>
                    <option value="LOGIN">Login</option>
                  </CFormSelect>
                </CCol>
                <CCol md={4}>
                  <CFormSelect
                    name="entity_type"
                    value={filters.entity_type}
                    onChange={handleFilterChange}
                  >
                    <option value="">All Entity Types</option>
                    <option value="customer">Customer</option>
                    <option value="account">Account</option>
                    <option value="balance_operation">Balance Operation</option>
                    <option value="user">User</option>
                  </CFormSelect>
                </CCol>
                <CCol md={4}>
                  <CButton color="primary" onClick={loadLogs} className="w-100">
                    <CIcon icon={cilFilter} className="me-2" />
                    Apply Filters
                  </CButton>
                </CCol>
              </CRow>

              {/* Table */}
              {loading ? (
                <div className="text-center py-5">
                  <CSpinner color="primary" />
                </div>
              ) : logs.length === 0 ? (
                <div className="text-center py-5 text-muted">
                  <p>No audit logs found.</p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <CTable hover responsive>
                    <CTableHead>
                      <CTableRow>
                        <CTableHeaderCell style={{ width: '60px' }}>Icon</CTableHeaderCell>
                        <CTableHeaderCell>Action</CTableHeaderCell>
                        <CTableHeaderCell>Entity</CTableHeaderCell>
                        <CTableHeaderCell>Entity ID</CTableHeaderCell>
                        <CTableHeaderCell>User</CTableHeaderCell>
                        <CTableHeaderCell>Details</CTableHeaderCell>
                        <CTableHeaderCell>Timestamp</CTableHeaderCell>
                      </CTableRow>
                    </CTableHead>
                    <CTableBody>
                      {logs.map((log) => (
                        <CTableRow key={log.id}>
                          <CTableDataCell className="text-center">
                            <span style={{ fontSize: '1.5rem' }}>
                              {getEntityIcon(log.entity)}
                            </span>
                          </CTableDataCell>
                          <CTableDataCell>
                            <CBadge color={getActionColor(log.action)}>
                              {log.action}
                            </CBadge>
                          </CTableDataCell>
                          <CTableDataCell>
                            <strong>{log.entity}</strong>
                          </CTableDataCell>
                          <CTableDataCell>{log.entity_id || '-'}</CTableDataCell>
                          <CTableDataCell>
                            {log.actor_user?.email || `User #${log.actor_id}`}
                          </CTableDataCell>
                          <CTableDataCell>
                            <small className="text-muted">
                              {log.after || log.before ? (
                                <code style={{ fontSize: '0.8rem' }}>
                                  {JSON.stringify(log.after || log.before).substring(0, 100)}...
                                </code>
                              ) : (
                                '-'
                              )}
                            </small>
                          </CTableDataCell>
                          <CTableDataCell>
                            <small>{new Date(log.created_at).toLocaleString()}</small>
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

export default Audit;
