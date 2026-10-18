// Tests de la lógica de orquestación de .claude/workflows/agentic-implement.js con agentes simulados.
// Ejecutar: node .claude/bin/test_workflow.mjs   (sin llamadas reales: agent() y parallel() son dobles)
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(here, '..', 'workflows', 'agentic-implement.js'), 'utf8').replace(/^export const meta/m, 'const meta')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const script = new AsyncFunction('agent', 'parallel', 'phase', 'log', 'args', source)

const PLAN = {
  waves: [1, 2], acceptance: true, type: 'feature', verify: ['tests'], max_fix_cycles: 2, baseline: true,
  work_packages: { 1: ['WP-01', 'WP-02'], 2: ['WP-03'] },
  agents: { 'WP-01': 'implementer', 'WP-02': 'implementer', 'WP-03': 'implementer' },
  wave_of: { 'WP-01': 1, 'WP-02': 1, 'WP-03': 2 },
}

// Escenario configurable: cada clave sobrescribe el comportamiento por defecto (todo bien).
async function simulate(scenario = {}, args = {}) {
  const calls = []
  let reviewRound = 0
  let qaRound = 0
  const agent = async (prompt, opts) => {
    calls.push({ type: opts.agentType, label: opts.label, prompt })
    switch (opts.agentType) {
      case 'gatekeeper': {
        const cmd = prompt.split('agentic.py ')[1].trim()
        if (scenario.gate && scenario.gate(cmd)) return scenario.gate(cmd)
        if (cmd === 'pipeline-plan') return { exit_code: 0, output: JSON.stringify({ ...PLAN, ...(scenario.plan || {}) }) }
        if (cmd === 'verify') return { exit_code: 0, output: JSON.stringify({ ok: true, blocking: [], preexisting_failures: [], phases: [{ name: 'tests', passed: true }] }) }
        if (cmd === 'baseline') return { exit_code: 0, output: JSON.stringify({ phases: [{ name: 'tests', passed: true }], preexisting_failures: [] }) }
        return { exit_code: 0, output: 'RESULTADO: OK' }
      }
      case 'test-author':
        return scenario.testAuthor || { status: 'DONE', coverage: [{ ac: 'AC-001', tests: ['test_ac_001'] }], blocker: null }
      case 'implementer': {
        const wp = opts.label.split(' ')[0]
        return { status: 'DONE', wp, files: [], checks: [], internal_decisions: [], blocker: null }
      }
      case 'reviewer':
        reviewRound += 1
        return scenario.review ? scenario.review(reviewRound) : { status: 'PASS', findings: [] }
      case 'verifier':
        return scenario.verifier || { is_real: true, confidence: 0.9, reasoning: 'se sostiene' }
      case 'qa':
        qaRound += 1
        return scenario.qa ? scenario.qa(qaRound) : { status: 'PASS', plan: ['contratos'], defects: [], gaps: [] }
      default:
        throw new Error(`agentType inesperado: ${opts.agentType}`)
    }
  }
  const parallel = thunks => Promise.all(thunks.map(t => t()))
  const result = await script(agent, parallel, () => {}, () => {}, args)
  return { result, calls, gates: calls.filter(c => c.type === 'gatekeeper').map(c => c.prompt.split('agentic.py ')[1].trim()) }
}

const grave = (wp, severity = 'alta') => ({ severity, wp, file: 'src/a.py', line: 3, problem: 'p', evidence: 'e' })
const tests = []
const test = (name, fn) => tests.push({ name, fn })

test('camino feliz: ola 0, dos olas, verificación, revisión y QA en OK', async () => {
  const { result, calls, gates } = await simulate()
  assert.equal(result.result, 'OK')
  assert.equal(result.fix_cycles, 0)
  assert.ok(gates.includes('close-stage acceptance AT=done --expect red'), 'la ola 0 exige rojo')
  assert.ok(gates.includes('close-stage 1 WP-01=done WP-02=done'))
  assert.ok(gates.includes('close-stage 2 WP-03=done'))
  assert.deepEqual(calls.filter(c => c.type === 'implementer').map(c => c.label), ['WP-01', 'WP-02', 'WP-03'])
  assert.ok(gates.indexOf('verify') > gates.indexOf('close-stage 2 WP-03=done'), 'la verificación va después de las olas')
})

test('test-author con BLOCKER: se para en la ola 0 sin lanzar implementers', async () => {
  const { result, calls, gates } = await simulate({
    testAuthor: { status: 'BLOCKER', coverage: [], blocker: 'AC-003 no es observable' },
    gate: cmd => (cmd.startsWith('close-stage acceptance') ? { exit_code: 3, output: 'RESULTADO: REVISAR' } : null),
  })
  assert.equal(result.result, 'REVISAR')
  assert.equal(result.failed_stage, 'ola 0')
  assert.ok(gates.includes('close-stage acceptance AT=blocker --expect red'))
  assert.equal(calls.filter(c => c.type === 'implementer').length, 0)
})

test('una ola en REVISAR detiene el pipeline antes de la siguiente', async () => {
  const { result, calls } = await simulate({
    gate: cmd => (cmd.startsWith('close-stage 1 ') ? { exit_code: 3, output: 'FUERA DE PROPIEDAD' } : null),
  })
  assert.equal(result.failed_stage, 'ola 1')
  assert.ok(!calls.some(c => c.label === 'WP-03'), 'la ola 2 no se lanza')
})

test('verificación fallida: se para antes de revisar', async () => {
  const { result, calls } = await simulate({
    gate: cmd => (cmd === 'verify' ? { exit_code: 3, output: JSON.stringify({ ok: false, phases: [{ name: 'tests', passed: false }] }) } : null),
  })
  assert.equal(result.failed_stage, 'verificación')
  assert.ok(!calls.some(c => c.type === 'reviewer'))
})

test('hallazgo grave refutado con confianza: no bloquea', async () => {
  const { result } = await simulate({
    review: () => ({ status: 'FAIL', findings: [grave('WP-01')] }),
    verifier: { is_real: false, confidence: 0.9, reasoning: 'validado en el llamador' },
  })
  assert.equal(result.result, 'OK')
  assert.equal(result.review.refuted.length, 1)
  assert.equal(result.fix_cycles, 0)
})

test('refutación insegura: el hallazgo se mantiene y su WP se corrige', async () => {
  const { result, calls, gates } = await simulate({
    review: round => (round === 1 ? { status: 'FAIL', findings: [grave('WP-02')] } : { status: 'PASS', findings: [] }),
    verifier: { is_real: false, confidence: 0.4, reasoning: 'no estoy seguro' },
  })
  assert.equal(result.result, 'OK')
  assert.equal(result.fix_cycles, 1)
  const fix = calls.find(c => c.label === 'WP-02 (fix)')
  assert.ok(fix && fix.prompt.includes('Corrige WP-02'), 'el WP recibe sus defectos')
  assert.ok(gates.includes('close-stage 1 WP-02=done --fix'), 'la corrección cuenta como ciclo de fix')
  assert.ok(!calls.some(c => c.label === 'WP-01 (fix)'), 'solo se corrige el WP afectado')
})

test('defecto que no se arregla: tope de 2 ciclos y queda pendiente', async () => {
  const defect = { id: 'D1', severity: 'alta', wp: 'WP-03', kind: 'implementation', section: '6.2', repro: 'x' }
  const { result, calls } = await simulate({ qa: () => ({ status: 'FAIL', plan: [], defects: [defect], gaps: [] }) })
  assert.equal(result.result, 'REVISAR')
  assert.equal(result.fix_cycles, 2)
  assert.equal(calls.filter(c => c.label === 'WP-03 (fix)').length, 2)
  assert.ok(result.pending.some(p => p.type === 'tope de correcciones agotado' && p.id === 'D1'))
})

test('defecto de diseño: no se corrige en bucle, se devuelve como pendiente', async () => {
  const defect = { id: 'D2', severity: 'alta', wp: 'WP-01', kind: 'design', section: '6.3', repro: 'y' }
  const { result, calls } = await simulate({ qa: () => ({ status: 'FAIL', plan: [], defects: [defect], gaps: [] }) })
  assert.equal(result.result, 'REVISAR')
  assert.equal(result.fix_cycles, 0)
  assert.ok(!calls.some(c => (c.label || '').endsWith('(fix)')))
  assert.ok(result.pending.some(p => p.type === 'diseño' && p.id === 'D2'))
})

test('refactor: sin test-author, la suite existente es la línea base', async () => {
  const { calls, gates } = await simulate({ plan: { type: 'refactor' } })
  assert.ok(!calls.some(c => c.type === 'test-author'))
  assert.equal(gates[1], 'baseline')
  assert.equal(gates[2], 'acceptance --expect green')
})

test('línea base: va antes de la ola 0 y su resultado se guarda', async () => {
  const { result, gates } = await simulate()
  assert.equal(gates[1], 'baseline')
  assert.ok(gates.indexOf('baseline') < gates.indexOf('open-stage acceptance'))
  assert.deepEqual(result.baseline.preexisting_failures, [])
})

test('línea base con fallo previo: no bloquea; un comando que no se puede ejecutar, sí', async () => {
  const pre = await simulate({ gate: c => (c === 'baseline' ? { exit_code: 0, output: JSON.stringify({ phases: [], preexisting_failures: ['lint'] }) } : null) })
  assert.equal(pre.result.result, 'OK')
  assert.deepEqual(pre.result.baseline.preexisting_failures, ['lint'])
  const broken = await simulate({ gate: c => (c === 'baseline' ? { exit_code: 1, output: '{}' } : null) })
  assert.equal(broken.result.failed_stage, 'línea base')
})

test('sin comandos de verify no hay línea base', async () => {
  const { gates } = await simulate({ plan: { baseline: false } })
  assert.ok(!gates.includes('baseline'))
})

test('start_wave: se salta la línea base, la ola 0 y las olas anteriores', async () => {
  const { calls, gates } = await simulate({}, { start_wave: 2 })
  assert.ok(!gates.includes('baseline'))
  assert.ok(!calls.some(c => c.type === 'test-author'))
  assert.deepEqual(calls.filter(c => c.type === 'implementer').map(c => c.label), ['WP-03'])
})

test('un agente que falla queda como error y la ola sale en REVISAR', async () => {
  const failing = { gate: cmd => (cmd.startsWith('close-stage 1 ') ? { exit_code: 3, output: 'REVISAR' } : null) }
  const { result, gates } = await simulate(failing)
  assert.equal(result.failed_stage, 'ola 1')
  assert.ok(gates.some(g => g.startsWith('close-stage 1 ')))
})

let failed = 0
for (const { name, fn } of tests) {
  try {
    await fn()
    console.log(`ok   ${name}`)
  } catch (err) {
    failed += 1
    console.log(`FAIL ${name}\n     ${err.message}`)
  }
}
console.log(`\n${tests.length - failed}/${tests.length} escenarios OK`)
process.exit(failed ? 1 : 0)
