// Muscle group data ported from the original IronAtlas app.
// Keys are "muscle IDs" used throughout the system.

/** Maps exercise muscle label → which muscle IDs are activated */
export const MUSCLE_TO_IDS: Record<string, string[]> = {
  "Front Deltoids":  ["front_delts"],
  "Side Deltoids":   ["side_delts"],
  "Rear Deltoids":   ["rear_delts"],
  "Shoulders":       ["front_delts", "side_delts", "rear_delts"],
  "Deltoids":        ["front_delts", "side_delts", "rear_delts"],
  "Upper Chest":     ["upper_pecs"],
  "Middle Chest":    ["middle_pecs"],
  "Lower Chest":     ["lower_pecs"],
  "Chest":           ["upper_pecs", "middle_pecs", "lower_pecs"],
  "Upper Traps":     ["upper_traps"],
  "Upper Back":      ["upper_back", "upper_traps"],
  "Lower Back":      ["lower_back"],
  "Biceps":          ["biceps"],
  "Triceps":         ["triceps"],
  "Forearms":        ["forearms"],
  "Upper Abs":       ["upper_abs"],
  "Lower Abs":       ["lower_abs"],
  "Obliques":        ["obliques"],
  "Abs":             ["upper_abs", "lower_abs", "obliques"],
  "Glutes":          ["glutes"],
  "Quads":           ["quads"],
  "Calves":          ["calves"],
  "Hamstrings":      ["hamstrings"],
  "Hip Abductor":    ["hip_abductor"],
  "Hip Adductor":    ["hip_adductor"],
  "Hips":            ["hip_abductor", "hip_adductor"],
  "Neck":            ["neck"],
};

/** Human-readable display names */
export const GROUP_LABELS: Record<string, string> = {
  front_delts:   "Front Delts",
  side_delts:    "Side Delts",
  rear_delts:    "Rear Delts",
  upper_pecs:    "Upper Chest",
  middle_pecs:   "Mid Chest",
  lower_pecs:    "Lower Chest",
  upper_traps:   "Upper Traps",
  upper_back:    "Upper Back",
  lower_back:    "Lower Back",
  biceps:        "Biceps",
  triceps:       "Triceps",
  forearms:      "Forearms",
  upper_abs:     "Upper Abs",
  lower_abs:     "Lower Abs",
  obliques:      "Obliques",
  glutes:        "Glutes",
  quads:         "Quads",
  calves:        "Calves",
  hamstrings:    "Hamstrings",
  hip_abductor:  "Hip Abductor",
  hip_adductor:  "Hip Adductor",
  neck:          "Neck",
};

/** Training tips per muscle group */
export const TIPS: Record<string, string> = {
  front_delts:   "Warm up rotator cuffs before heavy pressing. Front delts get hit hard by chest presses — balance with rear work.",
  side_delts:    "Lateral raises are king. Keep ego in check — lighter weight, strict form, high reps build cannonball delts.",
  rear_delts:    "Most underdeveloped muscle. Face pulls and reverse flys should be in every program.",
  upper_pecs:    "Incline pressing is essential. 30–45° is optimal. Cables from low to high also hit the upper fibres well.",
  middle_pecs:   "Flat bench is the classic. Focus on full ROM and controlled negatives. Retract scapulae.",
  lower_pecs:    "Dips and decline pressing. Lean forward on dips for more lower chest emphasis.",
  upper_traps:   "Shrug up and slightly back, not forward. Hold at the top 1–2 seconds. Heavy carries build traps.",
  upper_back:    "Squeeze shoulder blades on every rep. Mix horizontal (rows) and vertical (pulldowns) pulls.",
  lower_back:    "Never round under load. Build endurance before strength. Bracing technique matters most.",
  biceps:        "Supinate fully at top for peak contraction. Strict form — no swinging. Vary grip width.",
  triceps:       "Lock out fully on extensions. Compound pressing already hits triceps — manage total volume.",
  forearms:      "Train grip 2–3x per week. Include both flexion and extension. High reps (15–20) respond well.",
  upper_abs:     "Anti-extension work (rollouts, dead bugs) builds more functional strength than crunches.",
  lower_abs:     "Hanging leg raises are gold standard. Focus on posterior pelvic tilt to engage lower fibres.",
  obliques:      "Both rotational and anti-rotational work matter. Pallof presses build real oblique strength.",
  glutes:        "Hip thrusts are the gold standard. Squeeze hard at lockout. Mix bilateral and unilateral.",
  quads:         "Squat depth matters — at least parallel. Front squats emphasise quads more than back squats.",
  calves:        "High volume (15–20 reps) and full ROM are key. Train both straight-leg and bent-knee variations.",
  hamstrings:    "Eccentric loading (Nordics, RDLs) prevents injury. Most people need more hamstring work.",
  hip_abductor:  "Important for hip stability and knee health. Don't skip these for athletic performance.",
  hip_adductor:  "Inner thigh strength prevents groin injuries. Use both machine work and sumo variations.",
  neck:          "Train carefully with light loads. Neck strength protects against concussions in contact sports.",
};

/** All valid muscle IDs — used to validate mesh names */
export const MUSCLE_IDS = new Set(Object.keys(GROUP_LABELS));
