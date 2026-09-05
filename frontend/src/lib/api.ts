import axios from 'axios'
import type {
  AuditLogResponse,
  BanditState,
  CustomerDetail,
  CustomerSummary,
  EscalationsResponse,
  Narrative,
  PolicyConfig,
  Report,
  ResolutionStatus,
  RunSnapshot,
  SimulateResult,
} from './types'

// In local dev this stays '/api' and Vite's proxy (vite.config.ts) forwards
// it to the backend on :8000. In a deployed static build there is no dev
// server to proxy through, so VITE_API_BASE_URL must be set at build time
// to the deployed backend's full URL (see render.yaml).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({ baseURL: API_BASE_URL, timeout: 30000 })

export async function fetchReport(): Promise<Report> {
  const { data } = await api.get<Report>('/report')
  return data
}

export async function fetchAuditLog(): Promise<AuditLogResponse> {
  const { data } = await api.get<AuditLogResponse>('/audit-log')
  return data
}

export async function runBatch(): Promise<Report> {
  const { data } = await api.post<Report>('/run-batch')
  return data
}

export async function fetchHealth(): Promise<{ status: string; client_mode: string; llm_mode: string }> {
  const { data } = await api.get('/health')
  return data
}

export async function fetchNarrative(transactionId: string): Promise<Narrative> {
  const { data } = await api.get<Narrative>(`/narrative/${transactionId}`)
  return data
}

export async function fetchEscalations(): Promise<EscalationsResponse> {
  const { data } = await api.get<EscalationsResponse>('/escalations')
  return data
}

export async function postEscalationAction(
  transactionId: string,
  action: Exclude<ResolutionStatus, 'open'>,
  note: string
): Promise<unknown> {
  const { data } = await api.post(`/escalations/${transactionId}/action`, { action, note })
  return data
}

export async function fetchBanditState(): Promise<BanditState> {
  const { data } = await api.get<BanditState>('/bandit-state')
  return data
}

export interface AskMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AskResponse {
  answer: string
  provider: 'real' | 'simulated'
}

export async function askAgent(question: string, history: AskMessage[]): Promise<AskResponse> {
  const { data } = await api.post<AskResponse>('/ask', { question, history }, { timeout: 60000 })
  return data
}

export interface OnePagerResponse {
  html: string
  provider: 'real' | 'simulated'
}

export async function fetchOnePager(): Promise<OnePagerResponse> {
  const { data } = await api.get<OnePagerResponse>('/onepager', { timeout: 60000 })
  return data
}

export async function simulatePolicy(policy: PolicyConfig): Promise<SimulateResult> {
  const { data } = await api.post<SimulateResult>('/simulate', policy)
  return data
}

export async function fetchSimulateDefaults(): Promise<PolicyConfig> {
  const { data } = await api.get<PolicyConfig>('/simulate/defaults')
  return data
}

export async function fetchCustomers(): Promise<{ customers: CustomerSummary[] }> {
  const { data } = await api.get<{ customers: CustomerSummary[] }>('/customers')
  return data
}

export async function fetchCustomerDetail(customerId: string): Promise<CustomerDetail> {
  const { data } = await api.get<CustomerDetail>(`/customers/${customerId}`)
  return data
}

export async function fetchRunHistory(): Promise<{ count: number; runs: RunSnapshot[] }> {
  const { data } = await api.get<{ count: number; runs: RunSnapshot[] }>('/run-history')
  return data
}
