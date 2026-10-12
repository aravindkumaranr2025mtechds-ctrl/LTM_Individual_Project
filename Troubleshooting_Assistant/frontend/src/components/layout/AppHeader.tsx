import {
  RotateCcw,
  ShieldCheck,
  Wrench,
} from 'lucide-react'

import {
  useTroubleshootingStore,
} from '../../store/troubleshootingStore'

export function AppHeader() {
  const view =
    useTroubleshootingStore((state) => state.view)

  const setView =
    useTroubleshootingStore((state) => state.setView)

  const resetSession =
    useTroubleshootingStore(
      (state) => state.resetSession,
    )

  return (
    <header className="relative z-30 border-b border-white/10 bg-[#071630]/85 text-white backdrop-blur-xl">

      <div className="mx-auto flex min-h-20 max-w-[1600px] items-center justify-between gap-5 px-5 py-3 sm:px-6 lg:px-8">

        <div className="flex min-w-0 items-center gap-3">

          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500/30 to-violet-500/30 text-cyan-300 ring-1 ring-white/10 shadow-lg shadow-blue-950/40">
            <Wrench size={21} />
          </div>

          <div className="min-w-0">

            <div className="truncate text-base font-semibold tracking-tight">
              Industrial Troubleshooting Assistant
            </div>

            <div className="mt-1 text-xs text-slate-300">
              Technical and workplace assistance
            </div>

          </div>

        </div>


        <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-slate-200 xl:flex">

          <ShieldCheck
            size={15}
            className="text-emerald-400"
          />

          Guided assistance

        </div>


        <div className="flex shrink-0 items-center gap-2">

          <div className="hidden rounded-xl border border-white/10 bg-white/5 p-1 sm:flex">

            <button
              type="button"
              onClick={() => setView('technician')}
              className={[
                'rounded-lg px-3 py-1.5 text-xs font-medium transition',
                view === 'technician'
                  ? 'bg-white text-slate-950 shadow-sm'
                  : 'text-slate-300 hover:bg-white/10 hover:text-white',
              ].join(' ')}
            >
              Simple view
            </button>

            <button
              type="button"
              onClick={() => setView('engineering')}
              className={[
                'rounded-lg px-3 py-1.5 text-xs font-medium transition',
                view === 'engineering'
                  ? 'bg-white text-slate-950 shadow-sm'
                  : 'text-slate-300 hover:bg-white/10 hover:text-white',
              ].join(' ')}
            >
              Technical details
            </button>

          </div>


          <button
            type="button"
            onClick={resetSession}
            title="Start over"
            aria-label="Start over"
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-white"
          >
            <RotateCcw size={16} />
          </button>

        </div>

      </div>

    </header>
  )
}
