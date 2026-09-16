/**
 * setup.mjs — first-run connection to the trip planner, and the connect form
 * reused on the settings page.
 *
 * The crew stores every trip in a self-hosted trip planner the user owns. Until
 * one is reachable and the login works, index.mjs shows SetupPage instead of the
 * trip or empty page. Two ways in: let the app run one in Docker (POST
 * /service/create), or point it at one the user already runs (POST /setup).
 */

import { createElement as h, useState, useEffect } from 'react'
import { Icon, Pill } from './theme.mjs'
import { getSetup, postJSON } from './data.mjs'
import { t } from './i18n.mjs'

const DEFAULT_ADDRESS = 'http://127.0.0.1:3000'

function Field({ label, hint, type, value, onChange, placeholder, disabled, inputMode }) {
  return h('label', { className: 'td-field' },
    h('span', { className: 'lbl' }, label, hint ? h('span', { className: 'hint' }, hint) : null),
    h('input', {
      type: type || 'text', value, disabled, placeholder, inputMode,
      onChange: (e) => onChange(e.target.value),
    }))
}

/**
 * Address / email / password with "Test connection" and "Save". Shared by the
 * setup page and the settings page. `onSaved` fires after a successful save so
 * the caller can refresh status and leave setup.
 */
export function ConnectForm({ initial, onSaved, saveLabel }) {
  const [address, setAddress] = useState((initial && initial.trek_url) || DEFAULT_ADDRESS)
  const [email, setEmail] = useState((initial && initial.email) || '')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState('') // '' | 'test' | 'save'
  const [msg, setMsg] = useState(null) // { good: bool, text }

  async function submit(testOnly) {
    setBusy(testOnly ? 'test' : 'save')
    setMsg(null)
    const body = { trek_url: address.trim(), email: email.trim(), test_only: testOnly }
    if (password) body.password = password
    const { ok, data } = await postJSON('/setup', body)
    setBusy('')
    if (ok) {
      setMsg({ good: true, text: testOnly ? t('setup_reachable_ok') : t('setup_saved') })
      if (!testOnly && onSaved) onSaved()
      return
    }
    let text
    if (data && data.reachable === false) text = t('setup_unreachable', { url: address.trim() })
    else if (data && data.authenticated === false) text = t('setup_unauth')
    else text = (data && data.error) || t('unknown_error')
    setMsg({ good: false, text })
  }

  return h('div', { className: 'td-form' },
    h(Field, { label: t('setup_address'), type: 'text', value: address, onChange: setAddress, placeholder: DEFAULT_ADDRESS, disabled: !!busy }),
    h(Field, { label: t('setup_email'), type: 'email', value: email, onChange: setEmail, placeholder: 'admin@example.com', disabled: !!busy }),
    h(Field, { label: t('setup_password'), type: 'password', value: password, onChange: setPassword, disabled: !!busy }),
    h('div', { className: 'td-form-row' },
      h(Pill, { small: true, disabled: !!busy, onClick: () => submit(true) }, busy === 'test' ? t('setup_testing') : t('setup_test')),
      h(Pill, { small: true, dark: true, disabled: !!busy, onClick: () => submit(false) }, busy === 'save' ? t('setup_saving') : (saveLabel || t('setup_save')))),
    msg ? h('div', { className: ['td-form-msg', msg.good ? 'ok' : 'bad'].join(' ') }, msg.text) : null)
}

/** "Run it for me": create the Docker-managed trip planner. */
function RunCard({ setup, onDone }) {
  const canDocker = !!(setup && setup.docker_available)
  const [email, setEmail] = useState((setup && setup.email) || '')
  const [password, setPassword] = useState('')
  const [port, setPort] = useState(String((setup && setup.port) || 3000))
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  async function start() {
    setBusy(true)
    setMsg(null)
    const { ok, data } = await postJSON('/service/create', {
      email: email.trim(), password, port: Number(port) || 3000,
    })
    setBusy(false)
    if (ok) {
      setMsg({ good: true, text: t('setup_created') })
      if (onDone) onDone()
      return
    }
    setMsg({ good: false, text: t('setup_create_failed', { error: (data && data.error) || t('unknown_error') }) })
  }

  return h('div', { className: 'td-setup-card' },
    h('h2', null, t('setup_run_title')),
    h('p', { className: 'sub' }, t('setup_run_desc')),
    h('div', { className: 'grow' },
      canDocker ? null : h('div', { className: 'td-form-msg bad', style: { marginTop: 0, marginBottom: 4 } }, t('setup_no_docker')),
      h(Field, { label: t('setup_email'), type: 'email', value: email, onChange: setEmail, placeholder: 'admin@example.com', disabled: busy || !canDocker }),
      h(Field, { label: t('setup_password'), hint: t('setup_password_hint'), type: 'password', value: password, onChange: setPassword, disabled: busy || !canDocker }),
      h(Field, { label: t('setup_port'), type: 'text', inputMode: 'numeric', value: port, onChange: setPort, disabled: busy || !canDocker })),
    h('div', { className: 'td-form-row' },
      h(Pill, { dark: true, disabled: busy || !canDocker, onClick: start }, busy ? t('setup_starting') : t('setup_start'))),
    msg ? h('div', { className: ['td-form-msg', msg.good ? 'ok' : 'bad'].join(' ') }, msg.text) : null)
}

/** "I already run one": connect to an existing trip planner. */
function HaveCard({ setup, onDone }) {
  return h('div', { className: 'td-setup-card' },
    h('h2', null, t('setup_have_title')),
    h('p', { className: 'sub' }, t('setup_have_desc')),
    h(ConnectForm, { initial: setup, onSaved: onDone }))
}

export function SetupPage({ onDone, onSkip }) {
  const [setup, setSetup] = useState(null)
  useEffect(() => {
    let on = true
    getSetup().then((s) => { if (on) setSetup(s) }).catch(() => { if (on) setSetup({}) })
    return () => { on = false }
  }, [])

  return h('div', { className: 'td-scroll' },
    h('div', { className: 'td-settings-bar' },
      h('div', { className: 'td-brand' }, h(Icon, { name: 'pin', size: 22, stroke: 2.2 }), t('brand'))),
    h('div', { className: 'td-setup' },
      h('div', { className: 'td-setup-hero' },
        h('h1', null, t('setup_h1')),
        h('p', null, t('setup_lead'))),
      h('div', { className: 'td-setup-cards' },
        h(RunCard, { setup, onDone }),
        h(HaveCard, { setup, onDone })),
      h('div', { className: 'td-setup-skip' },
        h('button', { type: 'button', onClick: onSkip }, t('setup_skip')))))
}
