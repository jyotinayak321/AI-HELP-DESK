import api from './axios';

export const submitIntake = (data) => api.post('/api/intakes', data);
export const confirmTicket = (data) => api.post('/api/tickets/confirm', data);
export const confirmMultiTicket = (data) => api.post('/api/tickets/confirm-multi', data);
export const listTickets = (params = {}) => api.get('/api/tickets', { params });
export const updateTicket = (ticketNumber, data) => api.patch(`/api/tickets/${ticketNumber}`, data);
export const getSimilarResolutions = (ticketNumber) => api.get(`/api/tickets/${ticketNumber}/similar-resolutions`);
export const getTicketHistory = (ticketNumber) => api.get(`/api/tickets/${ticketNumber}/history`);
export const reanalyzeIntake = (intakeId, data) => api.post(`/api/intakes/${intakeId}/reanalyze`, data);