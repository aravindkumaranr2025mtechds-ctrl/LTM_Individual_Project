import { AppHeader } from './components/layout/AppHeader'
import { SessionSidebar } from './components/layout/SessionSidebar'
import { WorkflowProgress } from './components/workflow/WorkflowProgress'

import { ReportIssueCard } from './features/troubleshooting/ReportIssueCard'
import { UnderstandIssuePlaceholder } from './features/troubleshooting/UnderstandIssuePlaceholder'
import { AssistanceResult } from './features/troubleshooting/AssistanceResult'

import {
  useTroubleshootingStore,
} from './store/troubleshootingStore'


function App() {
  const stage =
    useTroubleshootingStore(
      (state) => state.stage,
    )

  const view =
    useTroubleshootingStore(
      (state) => state.view,
    )

  const response =
    useTroubleshootingStore(
      (state) => state.assistantResponse,
    )


  return (
    <div className="app-shell-background relative min-h-screen overflow-hidden text-white">

      {/* Background glow */}
      <div className="pointer-events-none absolute inset-0">

        <div className="absolute -left-60 top-24 h-[520px] w-[760px] -rotate-12 rounded-[45%] bg-gradient-to-r from-blue-700/35 via-indigo-700/20 to-transparent blur-3xl" />

        <div className="absolute -right-52 bottom-[-120px] h-[600px] w-[850px] rotate-[-18deg] rounded-[48%] bg-gradient-to-l from-indigo-600/35 via-blue-700/20 to-transparent blur-3xl" />

        <div className="absolute right-[12%] top-[12%] h-72 w-72 rounded-full bg-violet-600/10 blur-3xl" />

        <div
          className="absolute inset-0 opacity-[0.10]"
          style={{
            backgroundImage:
              'radial-gradient(circle at center, rgba(148,163,184,0.24) 1px, transparent 1px)',
            backgroundSize: '26px 26px',
            maskImage:
              'linear-gradient(to bottom, transparent, black 18%, black 75%, transparent)',
          }}
        />

      </div>


      <AppHeader />

      <WorkflowProgress />


      <main className="relative z-10 mx-auto max-w-[1600px] px-4 py-8 sm:px-6 lg:px-8">

        <div className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_320px]">

          <div className="min-w-0">

            {stage === 'report' && (
              <ReportIssueCard />
            )}

            {stage === 'understand' && (
              <UnderstandIssuePlaceholder />
            )}

            {!['report', 'understand'].includes(stage) && (
              <AssistanceResult />
            )}


            {view === 'engineering' && (

              <section className="mt-6 rounded-3xl border border-violet-400/20 bg-[#050d20]/75 p-5 text-slate-200 shadow-2xl backdrop-blur-xl">

                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-violet-300">
                  Technical details
                </div>

                <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">

                  <div className="rounded-xl border border-white/10 bg-white/5 p-3">

                    <div className="text-xs text-slate-400">
                      Final outcome
                    </div>

                    <div className="mt-1 font-semibold text-white">
                      {
                        response
                          ?.final_outcome
                          ?.decision ??
                        'Not available'
                      }
                    </div>

                  </div>


                  <div className="rounded-xl border border-white/10 bg-white/5 p-3">

                    <div className="text-xs text-slate-400">
                      Evidence items
                    </div>

                    <div className="mt-1 font-semibold text-white">
                      {
                        response
                          ?.evidence_contract
                          ?.evidence_count ??
                        0
                      }
                    </div>

                  </div>


                  <div className="rounded-xl border border-white/10 bg-white/5 p-3">

                    <div className="text-xs text-slate-400">
                      Diagnosis confirmed
                    </div>

                    <div className="mt-1 font-semibold text-white">
                      {
                        response
                          ?.diagnosis_confirmed === true
                          ? 'Yes'
                          : 'No'
                      }
                    </div>

                  </div>


                  <div className="rounded-xl border border-white/10 bg-white/5 p-3">

                    <div className="text-xs text-slate-400">
                      Automatic execution
                    </div>

                    <div className="mt-1 font-semibold text-white">
                      {
                        response
                          ?.approved_for_automatic_execution === true
                          ? 'Approved'
                          : 'Not approved'
                      }
                    </div>

                  </div>

                </div>


                <p className="mt-4 text-xs leading-5 text-slate-400">
                  Detailed retrieval metadata and verifier
                  information remain separate from the normal
                  operator view.
                </p>

              </section>

            )}

          </div>


          <SessionSidebar />

        </div>

      </main>

    </div>
  )
}

export default App
