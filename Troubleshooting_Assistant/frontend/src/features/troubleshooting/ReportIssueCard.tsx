import {
  ArrowRight,
  Building2,
  Check,
  GraduationCap,
  MessageSquareText,
  UserRoundPlus,
  Wrench,
} from 'lucide-react'

import type {
  LucideIcon,
} from 'lucide-react'

import type {
  SupportArea,
} from '../../types/assistant'

import {
  useTroubleshootingStore,
} from '../../store/troubleshootingStore'


interface AreaDefinition {
  id: SupportArea
  title: string
  description: string
  icon: LucideIcon
  iconClass: string
  selectedGradient: string
  selectedNeonClass: string
}


const areas: AreaDefinition[] = [
  {
    id: 'technical',
    title: 'Machine / Technical Issue',
    description:
      'Equipment stopped, alarm, fault, unusual behaviour or performance problem.',
    icon: Wrench,
    iconClass:
      'bg-blue-100 text-blue-700',
    selectedGradient:
      'from-blue-950 via-blue-900 to-indigo-900',
    selectedNeonClass:
      'help-area-neon-technical',
  },

  {
    id: 'fresher',
    title: 'Fresher / New Joiner',
    description:
      'Onboarding, company process, access, team, salary or general workplace help.',
    icon: UserRoundPlus,
    iconClass:
      'bg-emerald-100 text-emerald-700',
    selectedGradient:
      'from-emerald-950 via-teal-900 to-slate-900',
    selectedNeonClass:
      'help-area-neon-fresher',
  },

  {
    id: 'trainee',
    title: 'Trainee / Intern',
    description:
      'Training, project, attendance, stipend, certificate or mentor support.',
    icon: GraduationCap,
    iconClass:
      'bg-violet-100 text-violet-700',
    selectedGradient:
      'from-indigo-950 via-violet-900 to-blue-950',
    selectedNeonClass:
      'help-area-neon-trainee',
  },

  {
    id: 'department',
    title: 'Department Help',
    description:
      'HR, Finance, IT, Admin, Training, Access or another workplace team.',
    icon: Building2,
    iconClass:
      'bg-orange-100 text-orange-700',
    selectedGradient:
      'from-amber-950 via-orange-900 to-slate-900',
    selectedNeonClass:
      'help-area-neon-department',
  },
]


const concerns: Record<
  SupportArea,
  string[]
> = {
  technical: [
    'Machine stopped',
    "Machine won't start",
    'Motor stalls / stops while running',
    'Alarm / error',
    'Unusual sound',
    'Performance issue',
    'Other technical issue',
  ],

  fresher: [
    'Onboarding',
    'Team / Manager',
    'Access / Login',
    'Laptop / IT',
    'Payroll / Salary',
    'Attendance / Leave',
    'Training',
    'Company process',
    'Other concern',
  ],

  trainee: [
    'Training / Course',
    'Project / Task',
    'Access / Login',
    'Attendance / Leave',
    'Stipend / Payment',
    'Certificate',
    'Mentor / Team',
    'Other concern',
  ],

  department: [
    'HR',
    'Finance / Payroll',
    'IT Support',
    'Admin / Facilities',
    'Training / L&D',
    'Access / Security',
    'Travel / Procurement',
    'I do not know the department',
  ],
}


const placeholders: Record<
  SupportArea,
  string
> = {
  technical:
    "Example: The motor stopped while running and I don't know why.",

  fresher:
    "Example: I joined recently and I haven't received laptop access.",

  trainee:
    "Example: My internship certificate is still pending. Whom should I contact?",

  department:
    "Example: My salary has not been credited and I don't know which team handles it.",
}


export function ReportIssueCard() {
  const supportArea =
    useTroubleshootingStore(
      (state) => state.supportArea,
    )

  const concern =
    useTroubleshootingStore(
      (state) => state.concern,
    )

  const description =
    useTroubleshootingStore(
      (state) => state.issueDescription,
    )

  const context =
    useTroubleshootingStore(
      (state) => state.context,
    )

  const setSupportArea =
    useTroubleshootingStore(
      (state) => state.setSupportArea,
    )

  const setConcern =
    useTroubleshootingStore(
      (state) => state.setConcern,
    )

  const setDescription =
    useTroubleshootingStore(
      (state) => state.setIssueDescription,
    )

  const updateContext =
    useTroubleshootingStore(
      (state) => state.updateContext,
    )

  const startSession =
    useTroubleshootingStore(
      (state) => state.startSession,
    )

  const setStage =
    useTroubleshootingStore(
      (state) => state.setStage,
    )


  const isAbbMotorStall =
    supportArea === 'technical' &&
    concern === 'Motor stalls / stops while running' &&
    context.manufacturer?.trim().toLowerCase() === 'abb'


  const canContinue =
    Boolean(
      supportArea &&
      concern &&
      description.trim() &&
      (
        !isAbbMotorStall ||
        context.abbRequest
      ),
    )


  function continueReview() {
    if (!canContinue) {
      return
    }

    startSession()
    setStage('understand')
  }


  return (
    <section>

      <div className="mb-7 flex items-start gap-4">

        <div className="adaptive-hero-icon flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ring-1 shadow-lg">
          <MessageSquareText size={22} />
        </div>

        <div>

          <h1 className="adaptive-hero-title text-3xl font-bold tracking-tight sm:text-[34px]">
            How can we
            <span className="adaptive-hero-accent">
              {' '}help you
            </span>
            {' '}today?
          </h1>

          <p className="adaptive-hero-subtitle mt-2 text-sm">
            Select the area that best matches your situation.
          </p>

        </div>

      </div>


      <div className="grid gap-4 sm:grid-cols-2">

        {areas.map((area) => {

          const selected =
            supportArea === area.id

          const Icon =
            area.icon

          return (
            <button
              key={area.id}
              type="button"
              onClick={() =>
                setSupportArea(area.id)
              }
              className={[
                `help-area-card help-area-${area.id} relative min-h-40 overflow-hidden rounded-2xl border p-5 text-left transition-all duration-200 hover:-translate-y-0.5`,
                selected
                  ? `border-2 bg-gradient-to-br ${area.selectedGradient} ${area.selectedNeonClass} text-white`
                  : 'border border-white/70 bg-white text-slate-900 shadow-[0_12px_35px_rgba(0,0,0,0.18)] hover:shadow-[0_18px_40px_rgba(30,64,175,0.24)]',
              ].join(' ')}
            >

              <div className="flex items-start justify-between gap-4">

                <div
                  className={[
                    'flex h-11 w-11 items-center justify-center rounded-xl',
                    area.iconClass,
                  ].join(' ')}
                >
                  <Icon size={20} />
                </div>


                {selected && (
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 text-white shadow-lg shadow-violet-950/40">
                    <Check size={15} />
                  </div>
                )}

              </div>


              <div
                className={[
                  'mt-4 text-sm font-bold',
                  selected
                    ? 'text-white'
                    : 'text-slate-900',
                ].join(' ')}
              >
                {area.title}
              </div>

              <div
                className={[
                  'mt-1.5 text-xs leading-5',
                  selected
                    ? 'text-blue-100/80'
                    : 'text-slate-600',
                ].join(' ')}
              >
                {area.description}
              </div>

            </button>
          )
        })}

      </div>


      {supportArea && (

        <div className="mt-8">

          <div className="text-sm font-semibold text-white">
            What do you need help with?
          </div>

          <p className="mt-1 text-xs text-blue-200/70">
            Select the closest option.
          </p>


          <div className="mt-4 flex flex-wrap gap-2.5">

            {concerns[supportArea].map(
              (item) => {

                const active =
                  concern === item

                return (
                  <button
                    key={item}
                    type="button"
                    onClick={() =>
                      setConcern(item)
                    }
                    className={[
                      'rounded-full border px-4 py-2.5 text-xs font-semibold transition-all',
                      active
                        ? 'border-violet-400 bg-gradient-to-r from-fuchsia-500 via-violet-500 to-indigo-500 text-white shadow-lg shadow-violet-950/30'
                        : 'border-blue-300/25 bg-blue-950/20 text-blue-100 hover:border-blue-300/50 hover:bg-blue-800/30',
                    ].join(' ')}
                  >
                    {item}
                  </button>
                )
              },
            )}

          </div>

        </div>

      )}


      {supportArea === 'technical' && concern && (

        <div className="mt-8 rounded-2xl border border-blue-300/15 bg-blue-950/25 p-5 backdrop-blur">

          <div className="flex flex-wrap items-center justify-between gap-2">

            <div className="text-sm font-semibold text-white">
              Technical details
            </div>

            <div className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-semibold text-blue-100/70">
              Optional
            </div>

          </div>


          <p className="mt-1 text-xs leading-5 text-blue-200/70">
            Enter only the details you know. These values are used
            as explicit technical context and are not guessed from
            your question.
          </p>


          <div className="mt-4 grid gap-4 sm:grid-cols-2">

            <label className="block">

              <span className="text-xs font-semibold text-blue-100">
                Manufacturer
              </span>

              <input
                type="text"
                value={context.manufacturer ?? ''}
                onChange={(event) =>
                  updateContext({
                    manufacturer:
                      event.target.value,
                  })
                }
                placeholder="Example: Siemens"
                autoComplete="off"
                className="mt-2 h-11 w-full rounded-xl border border-white/15 bg-[#07172f]/80 px-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-violet-400 focus:ring-4 focus:ring-violet-500/15"
              />

            </label>


            <label className="block">

              <span className="text-xs font-semibold text-blue-100">
                Alarm / Error number
              </span>

              <input
                type="text"
                value={context.alarmNumber ?? ''}
                onChange={(event) =>
                  updateContext({
                    alarmNumber:
                      event.target.value,
                  })
                }
                placeholder="Example: 16783"
                autoComplete="off"
                className="mt-2 h-11 w-full rounded-xl border border-white/15 bg-[#07172f]/80 px-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-violet-400 focus:ring-4 focus:ring-violet-500/15"
              />

            </label>

          </div>


          {isAbbMotorStall && (

            <div className="mt-5 border-t border-white/10 pt-5">

              <label className="block">

                <span className="text-xs font-semibold text-blue-100">
                  ABB guided request
                </span>

                <select
                  value={context.abbRequest ?? ''}
                  onChange={(event) =>
                    updateContext({
                      abbRequest:
                        event.target.value
                          ? (
                              event.target.value as
                                | 'list_possible_causes'
                                | 'review_reports'
                                | 'identify_cause'
                            )
                          : undefined,
                    })
                  }
                  className="mt-2 h-11 w-full rounded-xl border border-cyan-300/20 bg-[#07172f] px-4 text-sm text-white outline-none transition focus:border-cyan-300 focus:ring-4 focus:ring-cyan-400/10"
                >
                  <option value="">
                    Select what you need
                  </option>

                  <option value="list_possible_causes">
                    List manual causes
                  </option>

                  <option value="review_reports">
                    Review existing reports
                  </option>

                  <option value="identify_cause">
                    Can a cause be identified?
                  </option>
                </select>

              </label>

              <div className="mt-3 rounded-xl border border-cyan-300/15 bg-cyan-400/[0.06] px-4 py-3 text-xs leading-5 text-cyan-100/80">
                This uses the approved ABB Motor stalls
                troubleshooting workflow. The request is selected
                explicitly rather than inferred from your question.
              </div>

            </div>

          )}


          <p className="mt-3 text-[11px] leading-5 text-blue-200/55">
            If you do not know either value, leave it blank.
          </p>

        </div>

      )}


      {supportArea && concern && (

        <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur">

          <label
            htmlFor="issue-description"
            className="text-sm font-semibold text-white"
          >
            Ask your question
          </label>

          <p className="mt-1 text-xs text-blue-200/70">
            Describe what happened or what you need.
          </p>

          <textarea
            id="issue-description"
            value={description}
            onChange={(event) =>
              setDescription(
                event.target.value
              )
            }
            placeholder={
              placeholders[supportArea]
            }
            className="mt-3 min-h-32 w-full resize-y rounded-xl border border-white/15 bg-[#07172f]/80 px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-slate-400 focus:border-violet-400 focus:ring-4 focus:ring-violet-500/15"
          />

        </div>

      )}


      {supportArea && concern && (

        <div className="mt-6 flex justify-end">

          <button
            type="button"
            disabled={!canContinue}
            onClick={continueReview}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-indigo-500 to-blue-500 px-6 py-2.5 text-sm font-semibold text-white shadow-xl shadow-indigo-950/35 transition hover:-translate-y-0.5 hover:brightness-110 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Continue
            <ArrowRight size={16} />
          </button>

        </div>

      )}

    </section>
  )
}




