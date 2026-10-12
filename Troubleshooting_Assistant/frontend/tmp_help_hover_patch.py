from pathlib import Path
import re

card_path = Path(
    "src/features/troubleshooting/ReportIssueCard.tsx"
)

css_path = Path("src/index.css")

text = card_path.read_text(encoding="utf-8")
css = css_path.read_text(encoding="utf-8")


# =========================================================
# 1. Add stable CSS identity classes to every help-area card
# =========================================================

old = """                'relative min-h-40 overflow-hidden rounded-2xl border p-5 text-left transition-all duration-200 hover:-translate-y-0.5',"""

new = """                `help-area-card help-area-${area.id} relative min-h-40 overflow-hidden rounded-2xl border p-5 text-left transition-all duration-200 hover:-translate-y-0.5`,"""

if old not in text:
    raise SystemExit(
        "STOP: Base help-area card class was not found."
    )

text = text.replace(old, new, 1)


# =========================================================
# 2. Add selected state class without changing gradients
# =========================================================

pattern = re.compile(
    r"""selected\s*
\s*\?\s*`border-violet-400/80 bg-gradient-to-br \$\{area\.selectedGradient\} text-white shadow-\[0_0_0_2px_rgba\(139,92,246,0\.25\),0_18px_35px_rgba\(76,29,149,0\.28\)\]`
\s*:\s*'border-white/70 bg-white text-slate-900 shadow-\[0_12px_35px_rgba\(0,0,0,0\.18\)\] hover:shadow-\[0_18px_40px_rgba\(30,64,175,0\.24\)\]'"""
)

replacement = """selected
                  ? `help-area-selected bg-gradient-to-br ${area.selectedGradient} text-white`
                  : 'border-white/70 bg-white text-slate-900 shadow-[0_12px_35px_rgba(0,0,0,0.18)]'"""

updated, count = pattern.subn(
    replacement,
    text,
    count=1,
)

if count != 1:
    raise SystemExit(
        "STOP: Selected/unselected help-area class block was not found exactly once."
    )

text = updated


# =========================================================
# 3. Add CSS
# =========================================================

marker = "/* === HELP AREA HOVER AND SELECTED COLOURS === */"

if marker in css:
    raise SystemExit(
        "STOP: Help-area hover CSS already exists."
    )

new_css = r'''

/* === HELP AREA HOVER AND SELECTED COLOURS === */

.help-area-card {
  transition:
    background 220ms ease,
    border-color 220ms ease,
    box-shadow 220ms ease,
    transform 220ms ease;
}


/* ---------------------------------------------------------
   UNSELECTED HOVER COLOURS
   --------------------------------------------------------- */


/* Technical: light sky blue */

.help-area-technical:not(.help-area-selected):hover {
  background:
    linear-gradient(
      135deg,
      rgb(224 242 254),
      rgb(186 230 253)
    );

  border-color:
    rgb(56 189 248);

  box-shadow:
    0 0 0 1px rgba(56, 189, 248, 0.18),
    0 12px 32px rgba(14, 165, 233, 0.22);
}


/* Fresher: light green */

.help-area-fresher:not(.help-area-selected):hover {
  background:
    linear-gradient(
      135deg,
      rgb(220 252 231),
      rgb(187 247 208)
    );

  border-color:
    rgb(74 222 128);

  box-shadow:
    0 0 0 1px rgba(74, 222, 128, 0.18),
    0 12px 32px rgba(34, 197, 94, 0.20);
}


/* Trainee: light lavender */

.help-area-trainee:not(.help-area-selected):hover {
  background:
    linear-gradient(
      135deg,
      rgb(237 233 254),
      rgb(221 214 254)
    );

  border-color:
    rgb(167 139 250);

  box-shadow:
    0 0 0 1px rgba(167, 139, 250, 0.18),
    0 12px 32px rgba(139, 92, 246, 0.20);
}


/* Department: light peach */

.help-area-department:not(.help-area-selected):hover {
  background:
    linear-gradient(
      135deg,
      rgb(255 237 213),
      rgb(254 215 170)
    );

  border-color:
    rgb(251 146 60);

  box-shadow:
    0 0 0 1px rgba(251, 146, 60, 0.18),
    0 12px 32px rgba(249, 115, 22, 0.20);
}


/* ---------------------------------------------------------
   SELECTED CARD COLOURS
   Existing dark gradient is preserved.
   Only matching border + neon are added.
   --------------------------------------------------------- */

@keyframes technicalSelectedNeon {
  0%,
  100% {
    box-shadow:
      0 0 8px rgba(56, 189, 248, 0.20),
      0 18px 38px rgba(2, 132, 199, 0.18);
  }

  50% {
    box-shadow:
      0 0 5px rgba(224, 242, 254, 0.85),
      0 0 18px rgba(56, 189, 248, 0.72),
      0 0 32px rgba(14, 165, 233, 0.40),
      0 18px 42px rgba(2, 132, 199, 0.22);
  }
}


@keyframes fresherSelectedNeon {
  0%,
  100% {
    box-shadow:
      0 0 8px rgba(74, 222, 128, 0.18),
      0 18px 38px rgba(22, 163, 74, 0.17);
  }

  50% {
    box-shadow:
      0 0 5px rgba(220, 252, 231, 0.85),
      0 0 18px rgba(74, 222, 128, 0.70),
      0 0 32px rgba(34, 197, 94, 0.38),
      0 18px 42px rgba(22, 163, 74, 0.21);
  }
}


@keyframes traineeSelectedNeon {
  0%,
  100% {
    box-shadow:
      0 0 8px rgba(167, 139, 250, 0.19),
      0 18px 38px rgba(124, 58, 237, 0.18);
  }

  50% {
    box-shadow:
      0 0 5px rgba(237, 233, 254, 0.85),
      0 0 18px rgba(167, 139, 250, 0.72),
      0 0 32px rgba(139, 92, 246, 0.40),
      0 18px 42px rgba(124, 58, 237, 0.22);
  }
}


@keyframes departmentSelectedNeon {
  0%,
  100% {
    box-shadow:
      0 0 8px rgba(251, 146, 60, 0.19),
      0 18px 38px rgba(234, 88, 12, 0.18);
  }

  50% {
    box-shadow:
      0 0 5px rgba(255, 237, 213, 0.85),
      0 0 18px rgba(251, 146, 60, 0.72),
      0 0 32px rgba(249, 115, 22, 0.40),
      0 18px 42px rgba(234, 88, 12, 0.22);
  }
}


.help-area-technical.help-area-selected {
  border-width: 2px;

  border-color:
    rgba(56, 189, 248, 0.86);

  animation:
    technicalSelectedNeon
    760ms
    ease-in-out
    2;
}


.help-area-fresher.help-area-selected {
  border-width: 2px;

  border-color:
    rgba(74, 222, 128, 0.86);

  animation:
    fresherSelectedNeon
    760ms
    ease-in-out
    2;
}


.help-area-trainee.help-area-selected {
  border-width: 2px;

  border-color:
    rgba(167, 139, 250, 0.88);

  animation:
    traineeSelectedNeon
    760ms
    ease-in-out
    2;
}


.help-area-department.help-area-selected {
  border-width: 2px;

  border-color:
    rgba(251, 146, 60, 0.90);

  animation:
    departmentSelectedNeon
    760ms
    ease-in-out
    2;
}


/* Selected cards keep their dark/original gradient on hover */

.help-area-card.help-area-selected:hover {
  transform:
    translateY(-2px);
}


/* Accessibility */

@media (prefers-reduced-motion: reduce) {
  .help-area-technical.help-area-selected,
  .help-area-fresher.help-area-selected,
  .help-area-trainee.help-area-selected,
  .help-area-department.help-area-selected {
    animation: none !important;
  }
}
'''

css = css.rstrip() + new_css + "\n"

card_path.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)

css_path.write_text(
    css,
    encoding="utf-8",
    newline="\n",
)

print("Technical hover: LIGHT SKY BLUE")
print("Fresher hover: LIGHT GREEN")
print("Trainee hover: LIGHT LAVENDER")
print("Department hover: LIGHT PEACH")
print("Selected original gradients preserved: YES")
print("Selected coloured neon border: YES")
print("Selected border thickness: 2px")
