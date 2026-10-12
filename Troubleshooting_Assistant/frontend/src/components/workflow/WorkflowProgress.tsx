import {
  workflowSteps,
} from '../../lib/workflow'

import {
  useTroubleshootingStore,
} from '../../store/troubleshootingStore'

function getCopy(stage: string) {
  switch (stage) {
    case 'report':
      return 'Choose what you need help with'
    case 'understand':
      return 'Review your question'
    case 'evidence':
      return 'Find relevant information'
    case 'checks':
      return 'Answer follow-up questions'
    case 'decision':
      return 'See what to do next'
    case 'summary':
      return 'Summary'
    default:
      return 'Get help'
  }
}

export function WorkflowProgress() {
  const stage =
    useTroubleshootingStore((state) => state.stage)

  const currentIndex =
    workflowSteps.findIndex(
      (step) => step.id === stage,
    )

  const safeIndex =
    currentIndex < 0 ? 0 : currentIndex

  const total =
    workflowSteps.length

  const percentage =
    ((safeIndex + 1) / total) * 100

  return (
    <nav
      aria-label="Progress"
      className="relative z-20 border-b border-white/10 bg-[#081936]/70 text-white backdrop-blur-xl"
    >

      <div className="mx-auto max-w-[1600px] px-5 py-3 sm:px-6 lg:px-8">

        <div className="flex items-center justify-between gap-5">

          <div>

            <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-cyan-300">
              Step {safeIndex + 1} of {total}
            </div>

            <div className="mt-1 text-sm font-semibold text-white">
              {getCopy(stage)}
            </div>

          </div>


          <div className="w-32 sm:w-52">

            <div className="h-2.5 overflow-hidden rounded-full bg-white/10">

              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500 transition-all duration-300"
                style={{
                  width: `${percentage}%`,
                }}
              />

            </div>

          </div>

        </div>

      </div>

    </nav>
  )
}
