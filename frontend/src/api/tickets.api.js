import api from './axios';

export const submitIntake = (data) => api.post('/api/intakes', data);
export const confirmTicket = (data) => api.post('/api/tickets/confirm', data);
export const listTickets = (params = {}) => api.get('/api/tickets', { params });
export const updateTicket = (ticketNumber, data) => api.patch(`/api/tickets/${ticketNumber}`, data);