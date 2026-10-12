import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  CircleHelp,
  ExternalLink,
  LoaderCircle,
  ShieldAlert,
} from 'lucide-react'

import {
  sourcePageUrl,
} from '../../api/assistant'

import {
  useTroubleshootingStore,
} from '../../store/troubleshootingStore'

import type {
  FinalDecision,
} from '../../types/assistant'


const decisionContent: Record<
  FinalDecision,
  {
    title: string
    description: string
  }
> = {
  ANSWER: {
    title: 'Relevant information found',
    description:
      'Approved source evidence was found for your request.',
  },

  CLARIFY: {
    title: 'More information is needed',
    description:
      'The system needs an additional detail before it can continue safely.',
  },

  ABSTAIN: {
    title: 'Not enough verified evidence',
    description:
      'The available evidence is not sufficient for a supported conclusion.',
  },

  ESCALATE: {
    title: 'Expert review recommended',
    description:
      'This request should be reviewed by an authorized technician or specialist.',
  },
}


function asRecord(
  value: unknown,
): Record<string, unknown> | null {
  if (
    value &&
    typeof value === 'object' &&
    !Array.isArray(value)
  ) {
    return value as Record<string, unknown>
  }

  return null
}


function candidateText(
  value: unknown,
): string | null {
  if (typeof value === 'string') {
    return value.trim() || null
  }

  const record = asRecord(value)

  if (!record) {
    return null
  }

  for (const key of [
    'candidate_answer',
    'answer',
    'text',
    'content',
    'generated_text',
  ]) {
    const item = record[key]

    if (
      typeof item === 'string' &&
      item.trim()
    ) {
      return item.trim()
    }
  }

  return null
}


function extractAcceptedGroundedAnswer(
  value: unknown,
  depth = 0,
): string | null {
  if (depth > 5 || value == null) {
    return null
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const found =
        extractAcceptedGroundedAnswer(
          item,
          depth + 1,
        )

      if (found) {
        return found
      }
    }

    return null
  }

  const record = asRecord(value)

  if (!record) {
    return null
  }

  const verification =
    asRecord(record.verification)

  const verifier =
    asRecord(record.verifier)

  const statuses = [
    record.status,
    record.verification_status,
    record.synthesis_status,
    verification?.status,
    verifier?.status,
  ]

  const accepted =
    statuses.some(
      (status) =>
        status === 'accepted_for_review',
    )

  if (accepted) {
    for (const key of [
      'candidate_answer',
      'candidate',
      'answer',
      'generated_text',
      'text',
    ]) {
      const text =
        candidateText(record[key])

      if (text) {
        return text
      }
    }
  }

  for (const key of [
    'grounded_synthesis',
    'synthesis',
    'result',
    'generation',
    'verification_result',
  ]) {
    if (key in record) {
      const found =
        extractAcceptedGroundedAnswer(
          record[key],
          depth + 1,
        )

      if (found) {
        return found
      }
    }
  }

  return null
}


function friendlySourceName(
  filename?: string | null,
) {
  if (!filename) {
    return 'Approved manufacturer manual'
  }

  return filename
    .replace(/^[a-f0-9]{32}_/i, '')
    .replace(/\.pdf$/i, '')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}


function DecisionIcon({
  decision,
}: {
  decision: FinalDecision
}) {
  if (decision === 'ANSWER') {
    return <CheckCircle2 size={22} />
  }

  if (decision === 'CLARIFY') {
    return <CircleHelp size={22} />
  }

  if (decision === 'ESCALATE') {
    return <ShieldAlert size={22} />
  }

  return <AlertTriangle size={22} />
}


function extractQuestion(
  value: unknown,
): string | null {
  if (typeof value === 'string') {
    return value.trim() || null
  }

  if (
    value &&
    typeof value === 'object'
  ) {
    const record =
      value as Record<string, unknown>

    for (
      const key of [
        'text',
        'question',
        'message',
      ]
    ) {
      const candidate = record[key]

      if (
        typeof candidate === 'string' &&
        candidate.trim()
      ) {
        return candidate.trim()
      }
    }
  }

  return null
}


export function AssistanceResult() {
  const response =
    useTroubleshootingStore(
      (state) => state.assistantResponse,
    )

  const requestStatus =
    useTroubleshootingStore(
      (state) => state.requestStatus,
    )

  const requestError =
    useTroubleshootingStore(
      (state) => state.requestError,
    )

  const setStage =
    useTroubleshootingStore(
      (state) => state.setStage,
    )

  const clearAssistantResult =
    useTroubleshootingStore(
      (state) => state.clearAssistantResult,
    )


  function returnToQuestion() {
    clearAssistantResult()
    setStage('understand')
  }


  if (requestStatus === 'loading') {
    return (
      <section className="result-searching-shell rounded-3xl border border-white/10 bg-blue-950/30 p-8 text-white shadow-2xl backdrop-blur-xl">

        <div className="flex min-h-[300px] flex-col items-center justify-center text-center">

          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-violet-200">
            <LoaderCircle
              size={26}
              className="animate-spin"
            />
          </div>

          <h1 className="mt-5 text-2xl font-semibold">
            Searching approved technical knowledge
          </h1>

          <p className="mt-2 max-w-xl text-sm leading-6 text-blue-100/70">
            The request is being processed through the
            troubleshooting workflow and approved evidence sources.
          </p>

        </div>

      </section>
    )
  }


  if (
    requestStatus === 'error' ||
    !response
  ) {
    return (
      <section className="rounded-3xl border border-red-400/20 bg-blue-950/30 p-7 text-white shadow-2xl backdrop-blur-xl">

        <div className="flex items-start gap-4">

          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-400/10 text-red-200">
            <AlertTriangle size={21} />
          </div>

          <div>
            <div className="text-xs font-bold uppercase tracking-[0.14em] text-red-200">
              Request could not continue
            </div>

            <h1 className="mt-2 text-2xl font-semibold">
              We could not retrieve a supported result
            </h1>

            <p className="mt-3 text-sm leading-6 text-blue-100/75">
              {
                requestError ||
                'No assistant response was returned.'
              }
            </p>

            <button
              type="button"
              onClick={returnToQuestion}
              className="mt-5 inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10"
            >
              <ArrowLeft size={16} />
              Back to question
            </button>

          </div>

        </div>

      </section>
    )
  }


  const backendDecision =
    response.final_outcome?.decision ??
    'ABSTAIN'

  const evidence =
    response.evidence_contract?.items ?? []

  /*
   * UI safety guard:
   * never present an evidence-backed ANSWER when the normalized
   * evidence contract contains no evidence items.
   */
  const decision: FinalDecision =
    backendDecision === 'ANSWER' &&
    evidence.length === 0
      ? 'ABSTAIN'
      : backendDecision

  const decisionInfo =
    decisionContent[decision]

  const nextQuestion =
    extractQuestion(
      response.next_question,
    )


  const groundedAnswer =
    extractAcceptedGroundedAnswer(
      response.grounded_synthesis ??
      response.synthesis ??
      response,
    )

  const hasSupportedEvidence =
    decision === 'ANSWER' &&
    evidence.length > 0

  const evidenceCount =
    response.evidence_contract
      ?.evidence_count ??
    evidence.length

  const sourceResult =
    asRecord(
      response.source_result,
    )

  const sourceEvidence =
    asRecord(
      sourceResult?.evidence,
    )

  const symptomRouting =
    asRecord(
      sourceEvidence
        ?.abb_symptom_routing,
    )

  const matchedSymptom =
    typeof symptomRouting
      ?.selected_symptom === 'string'
      ? symptomRouting
          .selected_symptom
          .trim()
      : null

  const resultTitle =
    hasSupportedEvidence
      ? matchedSymptom
        ? `${evidenceCount} possible ${
            evidenceCount === 1
              ? 'cause'
              : 'causes'
          } found`
        : 'Manufacturer information found'
      : decisionInfo.title

  const resultDescription =
    hasSupportedEvidence
      ? matchedSymptom
        ? `Matched symptom: ${matchedSymptom}`
        : `${evidenceCount} approved source ${
            evidenceCount === 1
              ? 'record supports'
              : 'records support'
          } this result.`
      : decisionInfo.description

  const firstEvidence =
    evidence[0]

  const firstSourcePage =
    firstEvidence
      ?.page_numbers?.[0]

  const sameSourcePage =
    Boolean(
      firstEvidence &&
      evidence.length > 0 &&
      evidence.every(
        (item) =>
          item.document_id ===
            firstEvidence.document_id &&
          item.source_filename ===
            firstEvidence.source_filename &&
          item.page_numbers?.[0] ===
            firstSourcePage,
      ),
    )

  const canOpenSharedSource =
    Boolean(
      sameSourcePage &&
      firstEvidence?.document_id &&
      Number.isFinite(
        firstSourcePage,
      ),
    )

  const sharedSourceName =
    friendlySourceName(
      firstEvidence
        ?.source_filename,
    )

  return (
    <div
      className={[
        'space-y-6',
        hasSupportedEvidence
          ? 'result-received'
          : '',
      ].join(' ')}
    >

      <section
        className={[
          'rounded-3xl border border-white/10 bg-blue-950/30 p-6 text-white shadow-2xl backdrop-blur-xl lg:p-8',
          hasSupportedEvidence
            ? 'result-success-card'
            : '',
        ].join(' ')}
      >

        <div className="flex flex-wrap items-start justify-between gap-5">

          <div className="flex min-w-0 gap-4">

            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-violet-200">
              <DecisionIcon
                decision={decision}
              />
            </div>

            <div>

              <div className="text-xs font-bold uppercase tracking-[0.14em] text-violet-300">
                Troubleshooting result
              </div>

              <h1 className="mt-2 text-2xl font-semibold">
                {resultTitle}
              </h1>

              <p className="mt-2 max-w-3xl text-sm leading-6 text-blue-100/75">
                {resultDescription}
              </p>

            </div>

          </div>


          <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-blue-100">
            {decision}
          </div>

        </div>


        {groundedAnswer && (
          <div className="mt-6 rounded-2xl border border-cyan-300/25 bg-cyan-400/[0.08] p-5 shadow-[0_0_24px_rgba(34,211,238,0.08)]">
            <div className="text-xs font-bold uppercase tracking-[0.13em] text-cyan-200">
              What the manual suggests
            </div>

            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-white">
              {groundedAnswer}
            </p>

            <p className="mt-3 text-[11px] leading-5 text-cyan-100/60">
              Generated only from retrieved evidence and accepted
              for review by the deterministic verifier. This is not
              a confirmed machine diagnosis.
            </p>
          </div>
        )}


        {response.message &&
          !hasSupportedEvidence && (
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-5">

            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-blue-200/70">
              Guidance
            </div>

            <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-white">
              {response.message}
            </p>

          </div>
        )}


        {nextQuestion && (
          <div className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-400/10 p-5">

            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-200">
              Information needed
            </div>

            <p className="mt-2 text-sm leading-6 text-amber-50">
              {nextQuestion}
            </p>

          </div>
        )}


        <div className="mt-5 flex flex-wrap gap-3">

          <button
            type="button"
            onClick={returnToQuestion}
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            <ArrowLeft size={16} />
            Change question
          </button>

        </div>

      </section>


      <section
        className={[
          'rounded-3xl border border-white/10 bg-[#071a38]/80 p-6 text-white shadow-2xl backdrop-blur-xl lg:p-8',
          hasSupportedEvidence
            ? 'evidence-success-panel'
            : '',
        ].join(' ')}
      >

        <div className="flex flex-wrap items-start justify-between gap-4">

          <div>

            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-blue-300">
              <BookOpen size={15} />
              Manufacturer source
            </div>

            <h2 className="mt-2 text-xl font-semibold">
              Evidence behind this result
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-blue-100/65">
              This result is based only on the approved technical
              evidence shown below.
            </p>

          </div>


          <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-blue-100">
            {evidenceCount} supporting {
              evidenceCount === 1
                ? 'record'
                : 'records'
            }
          </div>

        </div>


        {evidence.length === 0 ? (

          <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-5 text-sm leading-6 text-blue-100/70">
            No source evidence was returned for this request.
          </div>

        ) : (

          <>

            <div className="mt-6 rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.07] p-5">

              <div className="flex flex-wrap items-center justify-between gap-4">

                <div className="min-w-0">

                  <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-cyan-200/75">
                    Source manual
                  </div>

                  <div className="mt-1 break-words text-base font-semibold text-white">
                    {sharedSourceName}
                  </div>

                  <div className="mt-1 text-xs leading-5 text-blue-100/65">
                    {
                      sameSourcePage &&
                      Number.isFinite(
                        firstSourcePage,
                      )
                        ? `Page ${firstSourcePage} \u2022 ${evidenceCount} supporting ${
                            evidenceCount === 1
                              ? 'record'
                              : 'records'
                          }`
                        : `${evidenceCount} approved evidence ${
                            evidenceCount === 1
                              ? 'record'
                              : 'records'
                          }`
                    }
                  </div>

                </div>


                {canOpenSharedSource && (

                  <a
                    href={
                      sourcePageUrl(
                        firstEvidence
                          .document_id as string,
                        firstSourcePage,
                      )
                    }
                    target="_blank"
                    rel="noreferrer"
                    className={[
                      'inline-flex items-center gap-2 rounded-xl border border-cyan-300/25 bg-cyan-300/10 px-4 py-2.5 text-xs font-semibold text-cyan-50 transition hover:bg-cyan-300/15',
                      hasSupportedEvidence
                        ? 'source-page-success-link'
                        : '',
                    ].join(' ')}
                  >
                    View manual page
                    <ExternalLink size={14} />
                  </a>

                )}

              </div>

            </div>


            <details className="group mt-5 rounded-2xl border border-white/10 bg-[#040d20]/35">

              <summary className="cursor-pointer list-none px-5 py-4 text-sm font-semibold text-blue-100 transition hover:bg-white/[0.04]">

                <div className="flex items-center justify-between gap-4">

                  <span>
                    Technical evidence details
                  </span>

                  <span className="text-xs font-medium text-blue-200/60">
                    {evidenceCount} {
                      evidenceCount === 1
                        ? 'record'
                        : 'records'
                    } &bull; Expand
                  </span>

                </div>

              </summary>


              <div className="space-y-4 border-t border-white/10 p-4 sm:p-5">

                {evidence.map(
                  (item, index) => {

                    const firstPage =
                      item.page_numbers?.[0]

                    const canOpenSource =
                      Boolean(
                        item.document_id &&
                        Number.isFinite(
                          firstPage,
                        ),
                      )

                    return (

                      <article
                        key={
                          item.evidence_id ||
                          `${index}`
                        }
                        className={[
                          'rounded-2xl border border-white/10 bg-white/[0.045] p-5',
                          hasSupportedEvidence
                            ? 'evidence-success-item'
                            : '',
                        ].join(' ')}
                      >

                        <div className="flex flex-wrap items-start justify-between gap-4">

                          <div className="min-w-0">

                            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-blue-300">
                              Evidence {index + 1}
                            </div>

                            <div className="mt-1 break-words text-sm font-semibold text-white">
                              {
                                friendlySourceName(
                                  item.source_filename,
                                ) ||
                                item.document_id ||
                                item.source_type ||
                                'Approved technical source'
                              }
                            </div>

                            {
                              item.page_numbers
                                ?.length > 0 &&
                              (
                                <div className="mt-1 text-xs text-blue-100/60">
                                  Page{
                                    item
                                      .page_numbers
                                      .length > 1
                                      ? 's'
                                      : ''
                                  }{' '}
                                  {
                                    item.page_numbers.join(
                                      ', ',
                                    )
                                  }
                                </div>
                              )
                            }

                          </div>


                          {canOpenSource && (

                            <a
                              href={
                                sourcePageUrl(
                                  item.document_id as string,
                                  firstPage,
                                )
                              }
                              target="_blank"
                              rel="noreferrer"
                              className={[
                                'inline-flex items-center gap-2 rounded-xl border border-blue-300/20 bg-blue-400/10 px-3 py-2 text-xs font-semibold text-blue-100 transition hover:bg-blue-400/15',
                                hasSupportedEvidence
                                  ? 'source-page-success-link'
                                  : '',
                              ].join(' ')}
                            >
                              View source page
                              <ExternalLink size={14} />
                            </a>

                          )}

                        </div>


                        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-blue-50/90">
                          {
                            item.content ||
                            'Evidence text was not provided.'
                          }
                        </p>

                      </article>

                    )
                  },
                )}

              </div>

            </details>

          </>

        )}


        <div className="mt-6 rounded-2xl border border-amber-200/15 bg-amber-300/[0.05] p-4">

          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-100/75">
            Cause not confirmed
          </div>

          <p className="mt-2 text-xs leading-5 text-slate-200/80">
            These are manufacturer-supported possibilities.
            The evidence does not confirm the exact machine cause
            and does not authorize automatic machine action.
          </p>

        </div>

      </section>

    </div>
  )
}
