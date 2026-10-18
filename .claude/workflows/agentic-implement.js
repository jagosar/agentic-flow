export const meta = {
  name: 'agentic-implement',
  description: 'Lleva architecture.md a código verificado: ola 0 (aceptación primero), olas en paralelo, verificación, revisión adversarial, QA y correcciones con tope.',
  phases: [
    { title: 'Preparar', detail: 'pipeline-plan: olas, WP, aceptación y tope de correcciones' },
    { title: 'Línea base', detail: 'estado de build, tipos, lint y tests antes de tocar nada' },
    { title: 'Ola 0', detail: 'test-author escribe la aceptación; debe quedar en rojo' },
    { title: 'Olas', detail: 'implementers en paralelo por ola, con propiedad verificada' },
    { title: 'Verificación', detail: 'build, tipos, lint, tests y aceptación en verde' },
    { title: 'Revisión', detail: 'reviewer y verificación adversarial de los hallazgos graves' },
    { title: 'QA', detail: 'pruebas exploratorias más allá de los AC' },
    { title: 'Corrección', detail: 'cada defecto vuelve a su WP, con tope de ciclos' },
  ],
}

// Entrada opcional: args = { start_wave: N } para retomar desde una ola (se salta la ola 0).
// El script solo orquesta: no toca la shell ni el disco. Lo determinista lo ejecuta el agente gatekeeper con
// agentic.py, y los guardarraíles (hook PreToolUse) aplican a cada agente igual que fuera de un workflow.
const opts = args || {}
const startWave = Number.isInteger(opts.start_wave) ? opts.start_wave : null
const AGENTIC = 'python3 .claude/bin/agentic.py'

// ---------- esquemas ----------
const GATE_SCHEMA = {
  type: 'object',
  required: ['exit_code', 'output'],
  properties: { exit_code: { type: 'integer' }, output: { type: 'string' } },
}
const SEVERITY = { type: 'string', enum: ['critica', 'alta', 'media', 'baja'] }
const AT_SCHEMA = {
  type: 'object',
  required: ['status', 'coverage', 'blocker'],
  properties: {
    status: { type: 'string', enum: ['DONE', 'BLOCKER'] },
    coverage: { type: 'array', items: { type: 'object', required: ['ac', 'tests'], properties: { ac: { type: 'string' }, tests: { type: 'array', items: { type: 'string' } } } } },
    blocker: { type: ['string', 'null'] },
  },
}
const REPORT_SCHEMA = {
  type: 'object',
  required: ['status', 'wp', 'files', 'checks', 'internal_decisions', 'blocker'],
  properties: {
    status: { type: 'string', enum: ['DONE', 'BLOCKER'] },
    wp: { type: 'string', pattern: '^WP-[0-9]+$' },
    files: { type: 'array', items: { type: 'string' } },
    checks: { type: 'array', items: { type: 'object', required: ['command', 'passed'], properties: { command: { type: 'string' }, passed: { type: 'boolean' }, detail: { type: 'string' } } } },
    internal_decisions: { type: 'array', items: { type: 'string' } },
    blocker: { type: ['object', 'null'], required: ['missing', 'section'], properties: { missing: { type: 'string' }, section: { type: 'string' }, options: { type: 'array', items: { type: 'string' } } } },
  },
}
const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['status', 'findings'],
  properties: {
    status: { type: 'string', enum: ['PASS', 'FAIL'] },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'wp', 'file', 'problem', 'evidence'],
        properties: { severity: SEVERITY, wp: { type: 'string' }, file: { type: 'string' }, line: { type: 'integer' }, problem: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
  },
}
const VERDICT_SCHEMA = {
  type: 'object',
  required: ['is_real', 'confidence', 'reasoning'],
  properties: { is_real: { type: 'boolean' }, confidence: { type: 'number', minimum: 0, maximum: 1 }, reasoning: { type: 'string' } },
}
const QA_SCHEMA = {
  type: 'object',
  required: ['status', 'plan', 'defects', 'gaps'],
  properties: {
    status: { type: 'string', enum: ['PASS', 'FAIL', 'BLOCKER'] },
    plan: { type: 'array', items: { type: 'string' } },
    defects: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'severity', 'wp', 'kind', 'section', 'repro'],
        properties: { id: { type: 'string' }, severity: SEVERITY, wp: { type: 'string' }, kind: { type: 'string', enum: ['implementation', 'design'] }, section: { type: 'string' }, repro: { type: 'string' } },
      },
    },
    gaps: { type: 'array', items: { type: 'string' } },
  },
}

// ---------- utilidades ----------
const safe = (p, label) => p.catch(err => { log(`${label} falló: ${String((err && err.message) || err)}`); return null })
const gate = (cmd, label) =>
  safe(agent(`Ejecuta exactamente este comando desde la raíz del repo y devuelve su código de salida y su salida completa:\n\n${AGENTIC} ${cmd}`,
    { agentType: 'gatekeeper', label, schema: GATE_SCHEMA }), label)
const lastJson = out => {
  const lines = String(out || '').trim().split('\n').filter(l => l.trim().startsWith('{'))
  try { return lines.length ? JSON.parse(lines[lines.length - 1]) : null } catch (e) { return null }
}
const BLOCKING = new Set(['critica', 'alta'])
const run = { result: 'REVISAR', stages: [], baseline: null, work_packages: {}, verification: null, review: null, qa: null, fix_cycles: 0, pending: [] }
const stop = (stage, detail, extra) => ({ ...run, failed_stage: stage, detail, ...(extra || {}) })

async function runWave(wave, wpIds, defectsByWp) {
  const fixing = !!defectsByWp
  const open = await gate(`open-stage ${wave}`, `open-stage ${wave}`)
  if (!open || open.exit_code !== 0) return { ok: false, open }
  const reports = await parallel(wpIds.map(wp => () => {
    const prompt = fixing
      ? `Corrige ${wp} según architecture.md. El código ya existe. Estos son los defectos que los jueces (revisor y QA) atribuyen a tu WP, en JSON:\n` +
        `${JSON.stringify(defectsByWp[wp])}\nNo te salgas del contrato, no toques ficheros ajenos ni los tests de aceptación, y deja en verde los tests de aceptación de tus AC.`
      : `Implementa ${wp} según architecture.md.`
    return safe(agent(prompt, { agentType: plan.agents[wp] || 'implementer', label: fixing ? `${wp} (fix)` : wp, schema: REPORT_SCHEMA }), wp)
  }))
  wpIds.forEach((wp, i) => { run.work_packages[wp] = reports[i] })
  const states = wpIds.map((wp, i) => `${wp}=${!reports[i] ? 'error' : reports[i].status === 'DONE' ? 'done' : 'blocker'}`)
  const close = await gate(`close-stage ${wave} ${states.join(' ')}${fixing ? ' --fix' : ''}`, `close-stage ${wave}`)
  const ok = !!close && close.exit_code === 0
  run.stages.push({ stage: fixing ? `ola ${wave} (fix)` : `ola ${wave}`, ok, check: close && close.output })
  return { ok, reports, close }
}

// ---------- Preparar ----------
phase('Preparar')
const planGate = await gate('pipeline-plan', 'pipeline-plan')
const plan = planGate && planGate.exit_code === 0 ? lastJson(planGate.output) : null
if (!plan) return stop('preparar', 'pipeline-plan falló: el manifiesto no es válido', { gate: planGate })

// ---------- Línea base ----------
// Antes de tocar nada: así, al final, una fase que ya fallaba es "fallo previo" y no se atribuye a ningún WP.
// Al retomar desde una ola (start_wave) se conserva la línea base de la ejecución original.
if (startWave === null && plan.baseline) {
  phase('Línea base')
  const base = await gate('baseline', 'baseline')
  run.baseline = base ? lastJson(base.output) : null
  if (!base || base.exit_code !== 0) return stop('línea base', 'algún comando de verify no se pudo ejecutar (no existe o superó el tiempo)', { gate: base })
}

// ---------- Ola 0 ----------
if (startWave === null && plan.acceptance) {
  phase('Ola 0')
  if (plan.type === 'refactor') {
    // En un refactor la aceptación es la suite existente: debe estar en verde antes de tocar nada.
    const base = await gate('acceptance --expect green', 'línea base')
    run.stages.push({ stage: 'línea base', ok: !!base && base.exit_code === 0, check: base && base.output })
    if (!base || base.exit_code !== 0) return stop('ola 0', 'la suite existente no está en verde antes del refactor', { gate: base })
  } else {
    const open = await gate('open-stage acceptance', 'open-stage acceptance')
    if (!open || open.exit_code !== 0) return stop('ola 0', 'no se pudo abrir la etapa de aceptación', { gate: open })
    const at = await safe(agent('Escribe los tests de aceptación según architecture.md.', { agentType: 'test-author', label: 'test-author', schema: AT_SCHEMA }), 'test-author')
    const state = at && at.status === 'DONE' ? 'done' : 'blocker'
    const close = await gate(`close-stage acceptance AT=${state} --expect red`, 'close-stage acceptance')
    run.stages.push({ stage: 'ola 0', ok: !!close && close.exit_code === 0, test_author: at, check: close && close.output })
    if (!close || close.exit_code !== 0) {
      return stop('ola 0', at && at.status === 'BLOCKER'
        ? 'el test-author no puede probar algún criterio: hay que revisar architecture.md'
        : 'la aceptación no quedó en rojo por el motivo correcto (o se tocaron ficheros ajenos)', { test_author: at })
    }
  }
}

// ---------- Olas ----------
phase('Olas')
for (const wave of plan.waves.filter(w => startWave === null || w >= startWave)) {
  const res = await runWave(wave, plan.work_packages[String(wave)], null)
  if (!res.ok) return stop(`ola ${wave}`, 'la ola terminó con bloqueos, informes ausentes o escrituras fuera de propiedad')
}

// ---------- Verificación, revisión, QA y correcciones ----------
while (true) {
  phase('Verificación')
  const v = await gate('verify', 'verify')
  run.verification = v ? lastJson(v.output) : null
  if (!v || v.exit_code !== 0) return stop('verificación', 'alguna fase de verificación falla (ver verification)')

  phase('Revisión')
  const openR = await gate('open-stage review', 'open-stage review')
  const review = await safe(agent('Revisa el código integrado según architecture.md.', { agentType: 'reviewer', label: 'reviewer', schema: FINDINGS_SCHEMA }), 'reviewer')
  if (!review) return stop('revisión', 'el revisor no devolvió informe')
  const graves = review.findings.filter(f => BLOCKING.has(f.severity))
  const verdicts = await parallel(graves.map(f => () =>
    safe(agent(`Intenta refutar este hallazgo del revisor, en JSON:\n${JSON.stringify(f)}`, { agentType: 'verifier', label: `verificar ${f.file}`, schema: VERDICT_SCHEMA }), 'verifier')))
  // Un hallazgo solo se descarta si el verificador lo refuta con confianza. La incertidumbre nunca rebaja un bloqueo.
  const confirmed = graves.filter((f, i) => !(verdicts[i] && verdicts[i].is_real === false && verdicts[i].confidence >= 0.7))
  const refuted = graves.filter(f => !confirmed.includes(f))
  const advisory = review.findings.filter(f => !BLOCKING.has(f.severity))
  await gate(`close-stage review REVIEW=${confirmed.length ? 'fail' : 'pass'}`, 'close-stage review')
  run.review = { confirmed, refuted, advisory, opened: !!openR && openR.exit_code === 0 }

  phase('QA')
  await gate('open-stage qa', 'open-stage qa')
  const qa = await safe(agent('Ejecuta la validación QA del sistema según architecture.md.', { agentType: 'qa', label: 'qa', schema: QA_SCHEMA }), 'qa')
  if (!qa) return stop('qa', 'QA no devolvió informe')
  await gate(`close-stage qa QA=${qa.status === 'PASS' ? 'pass' : 'fail'}`, 'close-stage qa')
  run.qa = qa

  const implDefects = [
    ...confirmed.map(f => ({ source: 'revisor', ...f })),
    ...qa.defects.filter(d => d.kind === 'implementation' && BLOCKING.has(d.severity)).map(d => ({ source: 'qa', ...d })),
  ].filter(d => plan.wave_of[d.wp] !== undefined)
  const designDefects = qa.defects.filter(d => d.kind === 'design')
  const unassigned = [...confirmed, ...qa.defects.filter(d => d.kind === 'implementation' && BLOCKING.has(d.severity))]
    .filter(d => plan.wave_of[d.wp] === undefined)
  run.pending = [...designDefects.map(d => ({ type: 'diseño', ...d })), ...unassigned.map(d => ({ type: 'sin WP', ...d }))]

  if (implDefects.length === 0) {
    run.result = qa.status === 'BLOCKER' || run.pending.some(p => BLOCKING.has(p.severity)) ? 'REVISAR' : 'OK'
    return run
  }
  if (run.fix_cycles >= plan.max_fix_cycles) {
    run.pending.push(...implDefects.map(d => ({ type: 'tope de correcciones agotado', ...d })))
    return run
  }

  run.fix_cycles += 1
  phase('Corrección')
  const byWp = {}
  for (const d of implDefects) (byWp[d.wp] = byWp[d.wp] || []).push(d)
  const waves = [...new Set(Object.keys(byWp).map(wp => plan.wave_of[wp]))].sort((a, b) => a - b)
  for (const wave of waves) {
    const ids = Object.keys(byWp).filter(wp => plan.wave_of[wp] === wave).sort()
    const res = await runWave(wave, ids, byWp)
    if (!res.ok) return stop(`corrección ola ${wave}`, 'la corrección terminó con bloqueos o escrituras fuera de propiedad')
  }
}
