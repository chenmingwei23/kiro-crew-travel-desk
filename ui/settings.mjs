/**
 * settings.mjs — the app's settings page: interface language (中文 / English),
 * the trip data service (status, address, and the advanced start / stop /
 * restart / backup controls that used to hide in the overflow menu), and a
 * short "about". Reached from the "..." menu; a sticky bar with Back on top.
 */

import { createElement as h, useState, useEffect } from 'react'
import { Icon, Pill, T } from './theme.mjs'
import { postJSON, getSetup, localizeHost } from './data.mjs'
import { t, getLang, setLang, LANGS } from './i18n.mjs'
import { ConnectForm, RunCard } from './setup.mjs'

function Section({ icon, title, sub, children }) {
  return h('section', { className: 'td-sec' },
    h('div', { className: 'hd' },
      h('span', { className: 'ic' }, h(Icon, { name: icon, size: 20 })),
      h('div', null, h('div', { className: 't' }, title), sub ? h('div', { className: 's' }, sub) : null)),
    children)
}

function LanguageSection() {
  const cur = getLang()
  return h(Section, { icon: 'globe', title: t('lang_section'), sub: t('lang_desc') },
    ...LANGS.map((l) => h('button', {
      key: l.code, type: 'button', className: ['td-choice', cur === l.code ? 'on' : ''].join(' '),
      onClick: () => setLang(l.code), 'aria-pressed': cur === l.code, lang: l.code,
    },
    h('div', null, h('div', { className: 't' }, l.label), h('div', { className: 's' }, l.hint)),
    h('span', { className: 'radio' }, cur === l.code ? h(Icon, { name: 'check', size: 14, stroke: 3 }) : null))))
}

function ServiceSection({ status, onRefresh, onToast }) {
  const [setup, setSetup] = useState(null)
  const [edit, setEdit] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState('')
  const trek = (status && status.trek) || {}
  const container = trek.container || {}
  const up = !!trek.running
  const connected = !!trek.connected
  const url = trek.url ? localizeHost(trek.url) : ''
  const email = (setup && setup.email) || ''
  const managed = !!trek.managed
  const showAdvanced = managed || !!container.docker
  const canRun = !connected && !up && !!(setup && setup.docker_available)
  const sourceNote = trek.login_source === 'detected' ? t('svc_login_detected')
    : trek.login_source === 'ticket' ? t('svc_login_ticket') : ''

  // Reload the connection settings (address + login email) after a refresh.
  useEffect(() => {
    let on = true
    getSetup().then((s) => { if (on) setSetup(s) }).catch(() => { /* offline */ })
    return () => { on = false }
  }, [status])

  async function run(action, labelKey) {
    const label = t(labelKey)
    setBusy(action)
    const { ok, data } = await postJSON(`/service/${action}`)
    setBusy('')
    if (onToast) onToast(ok ? t('act_done', { label }) : t('act_failed', { label, error: (data && data.error) || t('unknown_error') }))
    if (onRefresh) onRefresh()
  }

  return h(Section, { icon: 'database', title: t('svc_section'), sub: t('svc_desc') },
    h('div', { className: 'td-kv' },
      h('span', { className: 'k' }, t('svc_status')),
      h('span', { className: 'v' },
        h('span', { className: 'td-online', style: { background: connected ? T.ok : T.warn } }),
        connected ? t('svc_connected') : up ? t('svc_running_no_login') : t('svc_stopped'))),
    url ? h('div', { className: 'td-kv' },
      h('span', { className: 'k' }, t('svc_url')),
      h('span', { className: 'v' }, h('a', { href: url, target: '_blank', rel: 'noreferrer' }, url))) : null,
    h('div', { className: 'td-kv' },
      h('span', { className: 'k' }, t('svc_login')),
      h('span', { className: 'v' }, email || (trek.login_source === 'ticket' ? t('svc_login_ticket_only') : t('svc_not_connected')),
        sourceNote ? h('span', { className: 'td-kv-note' }, sourceNote) : null)),
    !connected && trek.auth_error ? h('div', { className: 'td-form-msg bad', style: { marginTop: 6 } }, trek.auth_error) : null,
    canRun ? h('div', { className: 'td-adv open' },
      h('div', { className: 'td-adv-title' }, t('svc_run')),
      h(RunCard, { setup, small: true, onDone: onRefresh })) : null,
    h('div', { className: 'td-adv' },
      h('button', { type: 'button', className: 'td-adv-toggle', onClick: () => setEdit((v) => !v), 'aria-expanded': edit },
        connected || email ? t('svc_edit') : t('svc_connect_existing'), h(Icon, { name: 'chevron', size: 14, style: { transform: (edit || (!connected && up)) ? 'rotate(180deg)' : 'none' } })),
      (edit || (!connected && up)) ? h(ConnectForm, { initial: setup, onSaved: () => { setEdit(false); if (onRefresh) onRefresh() } }) : null),
    showAdvanced ? h('div', { className: 'td-adv' },
      h('button', { type: 'button', className: 'td-adv-toggle', onClick: () => setAdvanced((v) => !v), 'aria-expanded': advanced },
        t('advanced'), h(Icon, { name: 'chevron', size: 14, style: { transform: advanced ? 'rotate(180deg)' : 'none' } })),
      advanced ? h('div', null,
        h('div', { className: 'note' }, t('svc_adv_note')),
        h('div', { className: 'row' },
          managed ? h(Pill, { small: true, disabled: !!busy, onClick: () => run('backup', 'act_backup') }, h(Icon, { name: 'archive', size: 14 }), busy === 'backup' ? t('svc_backup_busy') : t('svc_backup')) : null,
          up
            ? h(Pill, { small: true, disabled: !!busy, onClick: () => run('restart', 'act_restart') }, h(Icon, { name: 'refresh', size: 14 }), busy === 'restart' ? t('svc_restart_busy') : t('svc_restart'))
            : h(Pill, { small: true, disabled: !!busy, onClick: () => run('start', 'act_start') }, h(Icon, { name: 'play', size: 14 }), busy === 'start' ? t('svc_start_busy') : t('svc_start')),
          up ? h(Pill, { small: true, disabled: !!busy, onClick: () => run('stop', 'act_stop') }, h(Icon, { name: 'stop', size: 14 }), busy === 'stop' ? t('svc_stop_busy') : t('svc_stop')) : null)) : null) : null)
}

export function SettingsPage({ status, members, onBack, onRefresh, onToast }) {
  return h('div', { className: 'td-scroll' },
    h('div', { className: 'td-settings-bar' },
      h('button', { type: 'button', className: 'td-back', onClick: onBack }, h(Icon, { name: 'back', size: 16 }), t('back')),
      h('div', { className: 'td-brand' }, h(Icon, { name: 'pin', size: 22, stroke: 2.2 }), t('brand'))),
    h('div', { className: 'td-settings' },
      h('h1', null, t('settings')),
      h('p', { className: 'lead' }, t('about_app')),
      h(LanguageSection, null),
      h(ServiceSection, { status, onRefresh, onToast }),
      h(Section, { icon: 'info', title: t('about_section'), sub: t('about_team', { n: (members || []).length }) })))
}
