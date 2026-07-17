import api from './axios';

export const getAllApps = () => api.get('/api/admin/applications');
export const createApp = (data) => api.post('/api/admin/applications', data);
export const getOneApp = (appId) => api.get(`/api/admin/applications/${appId}`);
export const updateApp = (appId, data) => api.put(`/api/admin/applications/${appId}`, data);
export const deleteApp = (appId) => api.delete(`/api/admin/applications/${appId}`);
export const addPurpose = (appId, data) => api.post(`/api/admin/applications/${appId}/purposes`, data);
export const addSymptom = (appId, data) => api.post(`/api/admin/applications/${appId}/symptoms`, data);
export const getAllDeps = () => api.get('/api/admin/dependencies');
export const createDep = (data) => api.post('/api/admin/dependencies', data);
export const deleteDep = (depId) => api.delete(`/api/admin/dependencies/${depId}`);
export const seedDatabase = () => api.post('/api/admin/seed');