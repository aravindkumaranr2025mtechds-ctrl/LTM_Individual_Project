import { create } from 'zustand'

import type {
  AssistantResponse,
  SupportArea,
  TechnicalContext,
  UserView,
  WorkflowStage,
} from '../types/assistant'

export type AssistantRequestStatus =
  | 'idle'
  | 'loading'
  | 'success'
  | 'error'

interface TroubleshootingState {
  stage: WorkflowStage
  view: UserView
  sessionActive: boolean

  context: TechnicalContext
  issueDescription: string

  supportArea: SupportArea | null
  concern: string

  assistantResponse: AssistantResponse | null
  requestStatus: AssistantRequestStatus
  requestError: string | null

  setStage: (stage: WorkflowStage) => void
  setView: (view: UserView) => void

  setIssueDescription: (
    description: string
  ) => void

  setSupportArea: (
    area: SupportArea | null
  ) => void

  setConcern: (
    concern: string
  ) => void

  updateContext: (
    context: Partial<TechnicalContext>
  ) => void

  beginAssistantRequest: () => void

  setAssistantResponse: (
    response: AssistantResponse
  ) => void

  setAssistantError: (
    message: string
  ) => void

  clearAssistantResult: () => void

  startSession: () => void
  resetSession: () => void
}

const initialContext: TechnicalContext = {}

export const useTroubleshootingStore =
  create<TroubleshootingState>((set) => ({
    stage: 'report',
    view: 'technician',
    sessionActive: false,

    context: initialContext,
    issueDescription: '',

    supportArea: null,
    concern: '',

    assistantResponse: null,
    requestStatus: 'idle',
    requestError: null,

    setStage: (stage) =>
      set({ stage }),

    setView: (view) =>
      set({ view }),

    setIssueDescription: (
      issueDescription
    ) =>
      set({ issueDescription }),

    setSupportArea: (
      supportArea
    ) =>
      set({
        supportArea,
        concern: '',
        assistantResponse: null,
        requestStatus: 'idle',
        requestError: null,
      }),

    setConcern: (
      concern
    ) =>
      set({ concern }),

    updateContext: (context) =>
      set((state) => ({
        context: {
          ...state.context,
          ...context,
        },
      })),

    beginAssistantRequest: () =>
      set({
        assistantResponse: null,
        requestStatus: 'loading',
        requestError: null,
      }),

    setAssistantResponse: (
      assistantResponse
    ) =>
      set({
        assistantResponse,
        requestStatus: 'success',
        requestError: null,
      }),

    setAssistantError: (
      requestError
    ) =>
      set({
        assistantResponse: null,
        requestStatus: 'error',
        requestError,
      }),

    clearAssistantResult: () =>
      set({
        assistantResponse: null,
        requestStatus: 'idle',
        requestError: null,
      }),

    startSession: () =>
      set({
        sessionActive: true,
      }),

    resetSession: () =>
      set({
        stage: 'report',
        view: 'technician',
        sessionActive: false,

        context: {},
        issueDescription: '',

        supportArea: null,
        concern: '',

        assistantResponse: null,
        requestStatus: 'idle',
        requestError: null,
      }),
  }))
