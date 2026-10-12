import {
  ArrowLeft,
  ArrowRight,
  LoaderCircle,
} from 'lucide-react'

import {
  assistantTurn,
} from '../../api/assistant'

import {
  useTroubleshootingStore,
} from '../../store/troubleshootingStore'

const areaNames = {
  technical: 'Machine / Technical Issue',
  fresher: 'Fresher / New Joiner',
  trainee: 'Trainee / Intern',
  department: 'Department Help',
}

export function UnderstandIssuePlaceholder() {
  const description =
    useTroubleshootingStore(
      (state) => state.issueDescription,
    )

  const supportArea =
    useTroubleshootingStore(
      (state) => state.supportArea,
    )

  const concern =
    useTroubleshootingStore(
      (state) => state.concern,
    )

  const context =
    useTroubleshootingStore(
      (state) => state.context,
    )


  const requestStatus =
    useTroubleshootingStore(
      (state) => state.requestStatus,
    )

  const setStage =
    useTroubleshootingStore(
      (state) => state.setStage,
    )

  const beginAssistantRequest =
    useTroubleshootingStore(
      (state) => state.beginAssistantRequest,
    )

  const setAssistantResponse =
    useTroubleshootingStore(
      (state) => state.setAssistantResponse,
    )

  const setAssistantError =
    useTroubleshootingStore(
      (state) => state.setAssistantError,
    )

  async function handleFindHelp() {
    const query = description.trim()

    if (!query) {
      setAssistantError(
        'Please describe the issue before continuing.',
      )
      return
    }

    /*
     * Workplace support is deliberately NOT routed into
     * the industrial troubleshooting backend.
     */
    if (supportArea !== 'technical') {
      beginAssistantRequest()

      setAssistantError(
        'The workplace-support backend is not connected yet. ' +
        'The current live workflow is available for Machine / Technical Issue.',
      )

      setStage('evidence')
      return
    }

    const isAbbMotorStall =
      concern ===
        'Motor stalls / stops while running' &&
      context.manufacturer
        ?.trim()
        .toLowerCase() === 'abb'


    if (isAbbMotorStall) {

      if (!context.abbRequest) {
        setAssistantError(
          'Select the ABB guided request before continuing.',
        )

        return
      }


      beginAssistantRequest()
      setStage('evidence')

      try {
        const response =
          await assistantTurn({
            mode: 'abb_stall',
            user_message: query,

            answers: {
              requested_information:
                context.abbRequest,
            },
          })

        setAssistantResponse(response)
      }
      catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : 'The ABB guided request failed.'

        setAssistantError(message)
      }

      return
    }


    /*
     * The selected technical concern is explicit user input.
     * Include it in the retrieval query instead of leaving the
     * concern as presentation-only UI state.
     *
     * The original user message remains unchanged.
     */
    const retrievalQuery =
      supportArea === 'technical' && concern
        ? `${concern}. ${query}`
        : query

    const answers: Record<string, unknown> = {
      query: retrievalQuery,
      top_k: 5,
    }

    /*
     * Only pass structured context if it has already been
     * explicitly supplied. Do not infer facts from free text.
     */
    if (context.manufacturer?.trim()) {
      answers.manufacturer =
        context.manufacturer.trim()
    }

    if (context.alarmNumber?.trim()) {
      answers.alarm_number =
        context.alarmNumber.trim()
    }

    if (context.machine?.trim()) {
      answers.equipment_type =
        context.machine.trim()
    }

    beginAssistantRequest()
    setStage('evidence')

    try {
      const response =
        await assistantTurn({
          mode: 'enterprise_evidence',
          user_message: query,
          answers,
        })

      setAssistantResponse(response)
    }
    catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'The troubleshooting request failed.'

      setAssistantError(message)
    }
  }

  const loading =
    requestStatus === 'loading'

  return (
    <section className="rounded-3xl border border-white/10 bg-blue-950/30 p-6 text-white shadow-2xl backdrop-blur-xl lg:p-8">

      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-violet-300">
        Your request
      </div>

      <h1 className="mt-2 text-3xl font-semibold">
        Check your question
      </h1>

      <p className="mt-2 text-sm text-blue-100/70">
        Confirm the details before continuing.
      </p>


      <div className="mt-7 grid gap-4 sm:grid-cols-2">

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">

          <div className="text-xs text-blue-200/70">
            Help area
          </div>

          <div className="mt-1 text-sm font-semibold text-white">
            {
              supportArea
                ? areaNames[supportArea]
                : 'Not selected'
            }
          </div>

        </div>


        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">

          <div className="text-xs text-blue-200/70">
            Concern
          </div>

          <div className="mt-1 text-sm font-semibold text-white">
            {concern || 'Not selected'}
          </div>

        </div>

      </div>


      {supportArea === 'technical' &&
        (
          context.manufacturer?.trim() ||
          context.alarmNumber?.trim()
        ) && (

          <div className="mt-4 grid gap-4 sm:grid-cols-2">

            <div className="rounded-2xl border border-blue-300/15 bg-blue-950/25 p-4">

              <div className="text-xs text-blue-200/70">
                Manufacturer
              </div>

              <div className="mt-1 text-sm font-semibold text-white">
                {
                  context.manufacturer?.trim() ||
                  'Not provided'
                }
              </div>

            </div>


            <div className="rounded-2xl border border-blue-300/15 bg-blue-950/25 p-4">

              <div className="text-xs text-blue-200/70">
                Alarm / Error number
              </div>

              <div className="mt-1 text-sm font-semibold text-white">
                {
                  context.alarmNumber?.trim() ||
                  'Not provided'
                }
              </div>

            </div>

          </div>

        )}


      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-5">

        <div className="text-xs text-blue-200/70">
          Your question
        </div>

        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-white">
          {description}
        </p>

      </div>


      {supportArea !== 'technical' && (
        <div className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-400/10 px-4 py-3 text-sm leading-6 text-amber-100">
          Workplace assistance is visible in the new interface,
          but its bounded backend router will be connected in a
          later project phase. Technical troubleshooting is the
          current live workflow.
        </div>
      )}


      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">

        <button
          type="button"
          disabled={loading}
          onClick={() =>
            setStage('report')
          }
          className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <ArrowLeft size={16} />
          Change
        </button>


        <button
          type="button"
          disabled={loading}
          onClick={handleFindHelp}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 to-blue-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-950/30 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {
            loading
              ? (
                  <>
                    <LoaderCircle
                      size={16}
                      className="animate-spin"
                    />
                    Searching approved knowledge
                  </>
                )
              : (
                  <>
                    Find relevant help
                    <ArrowRight size={16} />
                  </>
                )
          }
        </button>

      </div>

    </section>
  )
}



