export const meta = {
  name: 'agentic-wave',
  description: 'Prototipo: ejecuta una ola de architecture.md con implementers en paralelo, informes validados y verificación de propiedad.',
  phases: [
    { title: 'Preparar', detail: 'open-wave: validar, snapshot y WP de la ola' },
    { title: 'Implementar', detail: 'un implementer por WP, en paralelo' },
    { title: 'Verificar', detail: 'close-wave: propiedad de ficheros y estados en el ledger' },
  ],
}

// Entrada: args = { wave: <número de ola> }. El script no toca la shell ni el disco: todo lo determinista lo
// ejecuta el agente gatekeeper con agentic.py, y los guardarraíles (hook PreToolUse) siguen aplicando a cada agente.
const wave = args && Number.isInteger(args.wave) ? args.wave : null
if (wave === null) throw new Error('Falta args.wave (entero). Ejemplo: { "wave": 1 }')

const GATE_SCHEMA = {
  type: 'object',
  required: ['exit_code', 'output'],
  properties: {
    exit_code: { type: 'integer' },
    output: { type: 'string' },
  },
}

const PLAN_SCHEMA = {
  type: 'object',
  required: ['exit_code', 'wave', 'work_packages'],
  properties: {
    exit_code: { type: 'integer' },
    wave: { type: 'integer' },
    work_packages: { type: 'array', items: { type: 'string', pattern: '^WP-[0-9]+$' } },
  },
}

// El informe del implementer deja de ser texto libre: el runtime lo valida contra este esquema.
const REPORT_SCHEMA = {
  type: 'object',
  required: ['status', 'wp', 'files', 'checks', 'internal_decisions', 'blocker'],
  properties: {
    status: { type: 'string', enum: ['DONE', 'BLOCKER'] },
    wp: { type: 'string', pattern: '^WP-[0-9]+$' },
    files: { type: 'array', items: { type: 'string' } },
    checks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['command', 'passed'],
        properties: { command: { type: 'string' }, passed: { type: 'boolean' }, detail: { type: 'string' } },
      },
    },
    internal_decisions: { type: 'array', items: { type: 'string' } },
    blocker: {
      type: ['object', 'null'],
      required: ['missing', 'section'],
      properties: { missing: { type: 'string' }, section: { type: 'string' }, options: { type: 'array', items: { type: 'string' } } },
    },
  },
}

const gate = (command, label) =>
  agent(
    `Ejecuta exactamente este comando desde la raíz del repo y devuelve su código de salida y su salida completa:\n\n${command}`,
    { agentType: 'gatekeeper', label, schema: GATE_SCHEMA },
  )

phase('Preparar')
const plan = await agent(
  `Ejecuta exactamente: python3 .claude/bin/agentic.py open-wave ${wave}\n` +
    'La salida es JSON con "wave" y "work_packages". Devuélvelos tal cual, junto con el código de salida.',
  { agentType: 'gatekeeper', label: `open-wave ${wave}`, schema: PLAN_SCHEMA },
)
if (!plan || plan.exit_code !== 0 || plan.work_packages.length === 0) {
  return { result: 'REVISAR', stage: 'preparar', detail: 'open-wave falló: manifiesto inválido o ola sin WP', plan }
}
log(`Ola ${wave}: ${plan.work_packages.join(', ')}`)

phase('Implementar')
const reports = await parallel(
  plan.work_packages.map(wp => () =>
    agent(`Implementa ${wp} según architecture.md.`, { agentType: 'implementer', label: wp, schema: REPORT_SCHEMA })
      // Un agente que falla no tumba la ola: queda como "sin informe" y la ola sale en REVISAR.
      .catch(err => {
        log(`${wp} falló: ${String((err && err.message) || err)}`)
        return null
      }),
  ),
)

phase('Verificar')
const byWp = plan.work_packages.map((wp, i) => ({ wp, report: reports[i] }))
const states = byWp.map(r => `${r.wp}=${!r.report ? 'error' : r.report.status === 'DONE' ? 'done' : 'blocker'}`)
const check = await gate(`python3 .claude/bin/agentic.py close-wave ${wave} ${states.join(' ')}`, `close-wave ${wave}`)

const missing = byWp.filter(r => !r.report).map(r => r.wp)
const blockers = byWp.filter(r => r.report && r.report.status === 'BLOCKER')
const ownershipOk = !!check && check.exit_code === 0
const ok = missing.length === 0 && blockers.length === 0 && ownershipOk

return {
  result: ok ? 'OK' : 'REVISAR',
  wave,
  work_packages: byWp,
  sin_informe: missing,
  bloqueos: blockers.map(b => ({ wp: b.wp, blocker: b.report.blocker })),
  check_wave: check,
}
