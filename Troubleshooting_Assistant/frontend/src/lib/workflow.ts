import type { WorkflowStage } from '../types/assistant'

export interface WorkflowStep {
  id: WorkflowStage
  label: string
  shortLabel: string
}

export const workflowSteps: WorkflowStep[] = [
  {
    id: 'report',
    label: 'Report problem',
    shortLabel: 'Report',
  },
  {
    id: 'understand',
    label: 'Understand issue',
    shortLabel: 'Understand',
  },
  {
    id: 'evidence',
    label: 'Find evidence',
    shortLabel: 'Evidence',
  },
  {
    id: 'checks',
    label: 'Guided checks',
    shortLabel: 'Checks',
  },
  {
    id: 'decision',
    label: 'Review decision',
    shortLabel: 'Decision',
  },
  {
    id: 'summary',
    label: 'Resolution summary',
    shortLabel: 'Summary',
  },
]
