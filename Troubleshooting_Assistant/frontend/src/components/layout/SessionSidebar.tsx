import {
  BookOpen,
  Building2,
  CircleCheck,
  GraduationCap,
  ShieldCheck,
  UserRoundPlus,
  Wrench,
} from 'lucide-react'

import {
  useTroubleshootingStore,
} from '../../store/troubleshootingStore'


const areaInfo = {
  technical: {
    title: 'Technical help',
    icon: Wrench,
    accent: 'from-blue-400 to-cyan-400',
  },

  fresher: {
    title: 'Fresher / New Joiner',
    icon: UserRoundPlus,
    accent: 'from-emerald-400 to-cyan-400',
  },

  trainee: {
    title: 'Trainee / Intern',
    icon: GraduationCap,
    accent: 'from-violet-400 to-fuchsia-400',
  },

  department: {
    title: 'Department help',
    icon: Building2,
    accent: 'from-amber-400 to-orange-400',
  },
}


export function SessionSidebar() {
  const supportArea =
    useTroubleshootingStore(
      (state) => state.supportArea,
    )

  const concern =
    useTroubleshootingStore(
      (state) => state.concern,
    )

  const selected =
    supportArea
      ? areaInfo[supportArea]
      : null

  const SelectedIcon =
    selected?.icon


  return (
    <aside className="space-y-4">

      <section className="rounded-2xl border border-blue-300/20 bg-blue-900/30 p-5 text-white shadow-[0_18px_45px_rgba(0,0,0,0.18)] backdrop-blur-xl">

        <div className="flex items-center gap-3">

          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-blue-200">

            {SelectedIcon
              ? <SelectedIcon size={17} />
              : <BookOpen size={17} />}

          </div>

          <h2 className="text-sm font-semibold">
            Your request
          </h2>

        </div>


        {!selected ? (

          <p className="mt-4 text-xs leading-5 text-blue-100/60">
            Select one of the help areas to begin.
          </p>

        ) : (

          <dl className="mt-5 space-y-4">

            <div className="border-l-4 border-violet-400 pl-3">

              <dt className="text-xs text-blue-200/70">
                Help area
              </dt>

              <dd className="mt-1 text-sm font-bold text-white">
                {selected.title}
              </dd>

            </div>


            <div className="border-l-4 border-blue-500/60 pl-3">

              <dt className="text-xs text-blue-200/70">
                Concern
              </dt>

              <dd className="mt-1 text-sm font-semibold text-white">
                {concern || 'Choose a concern'}
              </dd>

            </div>

          </dl>

        )}

      </section>


      {supportArea && (

        <section className="rounded-2xl border border-blue-300/20 bg-blue-900/25 p-5 text-white shadow-[0_18px_45px_rgba(0,0,0,0.16)] backdrop-blur-xl">

          <div className="flex items-center gap-2">

            <ShieldCheck
              size={18}
              className="text-emerald-400"
            />

            <h2 className="text-sm font-semibold">
              {supportArea === 'technical'
                ? 'Technical safety'
                : 'Guided assistance'}
            </h2>

          </div>


          <div className="mt-4 space-y-4">

            <div className="flex gap-3 text-xs leading-5 text-blue-100/80">

              <CircleCheck
                size={16}
                className="mt-0.5 shrink-0 text-emerald-400"
              />

              <span>
                {supportArea === 'technical'
                  ? 'The assistant does not control or change the machine.'
                  : 'You do not need to know which department handles the issue.'}
              </span>

            </div>


            <div className="flex gap-3 text-xs leading-5 text-blue-100/80">

              <CircleCheck
                size={16}
                className="mt-0.5 shrink-0 text-emerald-400"
              />

              <span>
                {supportArea === 'technical'
                  ? 'Possible causes remain unconfirmed until supported.'
                  : 'Missing information can be requested before guidance is shown.'}
              </span>

            </div>

          </div>

        </section>

      )}

    </aside>
  )
}
