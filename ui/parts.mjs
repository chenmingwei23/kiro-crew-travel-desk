/**
 * parts.mjs — chrome shared by the trip page and the map view: the leader
 * chat (native ChatEmbed re-skinned to this page), the sticky chat card and
 * floating chat window, the team popover, the trip switcher and the overflow
 * menu. Service controls live on the settings page (settings.mjs), never here.
 */

import { createElement as h, useState, useRef, useCallback, useEffect } from 'react'
import { Icon, Pill, IconButton, Avatar, Avatars, T } from './theme.mjs'
import {
  LEADER_AGENT, leaderSlot, slotExists, sendToLeader, useClickAway, teamSummary, fmtRange, localizeHost,
  memberTitle, memberDuty,
} from './data.mjs'
import { t, useLang } from './i18n.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// Leader chat (native embed, with a plain fallback for old hosts)
// ─────────────────────────────────────────────────────────────────────────────

const ArrowUp = () => h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
  h('path', { d: 'm5 12 7-7 7 7' }), h('path', { d: 'M12 19V5' }))

/**
 * The first screen of a conversation that does not exist on the gateway yet
 * (the slot is created by its first message; until then the host chat can only
 * show an error). A greeting from the leader, example sentences to tap, and a
 * composer. After the send we wait for the slot to appear and hand over to the
 * real embed, so the transcript continues seamlessly.
 */
function FreshChat({ slot, placeholder, onReady, chips = true }) {
  const [draft, setDraft] = useState('')
  const [sent, setSent] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  async function send(text) {
    const msg = (text || draft).trim()
    if (!msg || sent) return
    setSent(msg); setDraft('')
    await sendToLeader(msg)
    // the POST returns when the stream opens; the slot exists by then, but
    // poll a little so the embed's first read never sees a 404
    for (let i = 0; i < 30 && alive.current; i++) {
      if (await slotExists(slot)) break
      await new Promise((r) => setTimeout(r, 500))
    }
    if (alive.current) onReady()
  }

  return h('div', { className: 'td-fresh' },
    h('div', { className: 'msgs' },
      h('div', { className: 'from' }, t('leader_short')),
      h('div', { className: 'bubble' }, t('fresh_hello')),
      sent ? h('div', { className: 'bubble me' }, sent) : null,
      sent ? h('div', { className: 'bubble typing', 'aria-label': t('leader_busy') }, h('i'), h('i'), h('i')) : null),
    !sent && chips ? h('div', { className: 'chips' }, ...t('examples').map((ex) => h(Pill, { key: ex, small: true, onClick: () => send(ex), title: t('send_to_leader') }, h('span', null, ex)))) : null,
    h('form', { onSubmit: (e) => { e.preventDefault(); send() } },
      h('input', { type: 'text', value: draft, disabled: !!sent, placeholder: sent ? t('leader_busy') : (placeholder || t('placeholder')), onChange: (e) => setDraft(e.target.value), 'aria-label': t('chat_fab') }),
      h('button', { type: 'submit', className: 'send', disabled: !!sent || !draft.trim(), title: t('send'), 'aria-label': t('send') }, h(ArrowUp))))
}

export function LeaderChat({ placeholder, chips = true }) {
  const lang = useLang()
  const slot = leaderSlot()
  const [exists, setExists] = useState(null) // null = checking
  useEffect(() => {
    let on = true
    let timer = null
    setExists(null)
    const probe = () => slotExists(slot).then((ok) => {
      if (!on) return
      setExists(ok)
      if (ok && timer) { clearInterval(timer); timer = null }
    })
    probe()
    // while the conversation does not exist, keep looking: the empty-state
    // chips (and the leader itself) can create it outside this component
    timer = setInterval(probe, 4000)
    return () => { on = false; if (timer) clearInterval(timer) }
  }, [slot, lang])

  const sdk = (typeof window !== 'undefined' && window.__kirocrew_modules)
    ? window.__kirocrew_modules['@kirocrew/app-sdk']
    : null
  if (!sdk || !sdk.ChatEmbed) {
    return h('div', { style: { padding: 20, fontSize: 14, color: T.muted, lineHeight: 1.6 } },
      h('div', { style: { fontWeight: 600, color: T.text, marginBottom: 6 } }, t('no_embed_title')),
      t('no_embed_body'))
  }
  if (exists === null) return h('div', { className: 'td-fresh' })
  if (exists === false) return h(FreshChat, { slot, placeholder, chips, onReady: () => setExists(true) })
  // `.td-embed` re-declares the dashboard's design tokens so the host chat
  // takes this page's palette and type (see theme.mjs "embedded chat").
  return h('div', { className: 'td-embed' },
    h(sdk.ChatEmbed, {
      key: slot,
      slotKey: slot,
      agent: LEADER_AGENT,
      frameless: true,
      startAtBottom: true,
      placeholder: placeholder || t('placeholder'),
    }))
}

// ─────────────────────────────────────────────────────────────────────────────
// Team popover
// ─────────────────────────────────────────────────────────────────────────────

const LAYERS = [['lead', 'layer_lead'], ['manage', 'layer_manage'], ['analyze', 'layer_analyst'], ['debate', 'layer_debate'], ['risk', 'layer_risk'], ['brief', 'layer_brief']]

function stateText(state) {
  const key = { working: 'state_working', done: 'state_done', blocked: 'state_blocked' }[state] || 'state_idle'
  return t(key)
}

export function TeamPopover({ members, onClose, style }) {
  const ref = useRef(null)
  useClickAway(ref, onClose)
  const byLayer = new Map()
  for (const m of members) {
    const k = m.layer || 'other'
    if (!byLayer.has(k)) byLayer.set(k, [])
    byLayer.get(k).push(m)
  }
  const order = LAYERS.map(([k]) => k).concat([...byLayer.keys()].filter((k) => !LAYERS.some(([l]) => l === k)))
  return h('div', { ref, className: 'td-float td-team', style },
    h('div', { style: { display: 'flex', alignItems: 'center', padding: '4px 6px 10px' } },
      h('div', null,
        h('div', { style: { fontSize: 15, fontWeight: 600 } }, t('team_header', { n: members.length })),
        h('div', { style: { fontSize: 12, color: T.muted, marginTop: 2 } }, t('team_sub'))),
      h('button', { type: 'button', onClick: onClose, 'aria-label': t('collapse'), style: { marginLeft: 'auto', border: 0, background: 'none', cursor: 'pointer', color: T.muted, display: 'inline-flex' } }, h(Icon, { name: 'x', size: 16 }))),
    ...order.filter((k) => byLayer.has(k)).map((k) => {
      const layer = LAYERS.find(([l]) => l === k)
      return h('div', { key: k },
        h('div', { style: { padding: '8px 6px 2px', fontSize: 11, color: T.muted, letterSpacing: '.04em' } }, layer ? t(layer[1]) : k),
        ...byLayer.get(k).map((m) => h('div', { key: m.id, className: 'td-team-row', title: memberDuty(m) },
          h(Avatar, { member: m, showState: true }),
          h('div', { style: { minWidth: 0 } },
            h('div', { className: 'n' }, memberTitle(m)),
            h('div', { className: 'd' }, memberDuty(m))),
          h('div', { className: ['st', m.state || ''].join(' ') }, stateText(m.state)))))
    }))
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat card (trip page, sticky right column)
// ─────────────────────────────────────────────────────────────────────────────

export function ChatCard({ members, className, chips = true, subtitle }) {
  const [teamOpen, setTeamOpen] = useState(false)
  const sum = teamSummary(members)
  return h('div', { className: ['td-chatcard', className || ''].join(' ') },
    h('div', { className: 'hd', style: { position: 'relative' } },
      h(Avatars, { members, max: 4, onClick: () => setTeamOpen((v) => !v) }),
      h('div', { className: 'who' },
        h('div', { className: 't' }, h('span', { className: ['td-online', sum.busy ? 'busy' : ''].join(' ') }), t('leader_title')),
        h('div', { className: 's' }, sum.busy ? t('leader_busy') : (sum.working ? sum.text : (subtitle || t('leader_idle_card'))))),
      teamOpen ? h(TeamPopover, { members, onClose: () => setTeamOpen(false), style: { top: 56, left: 12, right: 12, width: 'auto' } }) : null),
    h('div', { className: 'bd' }, h(LeaderChat, { chips })))
}

// ─────────────────────────────────────────────────────────────────────────────
// Floating chat (map view)
// ─────────────────────────────────────────────────────────────────────────────

export function ChatFloat({ members, onClose }) {
  const sum = teamSummary(members)
  const leader = sum.leader || { id: 'leader', title: '团长', title_en: 'Tour Leader', avatar_letter: '团', avatar_letter_en: 'TL' }
  return h('div', { className: 'td-float td-chatfloat' },
    h('div', { className: 'hd' },
      h(Avatar, { member: leader, size: 'lg' }),
      h('div', { style: { minWidth: 0 } },
        h('div', { className: 't' }, t('leader_title')),
        h('div', { className: 's' }, h('span', { className: ['td-online', sum.busy ? 'busy' : ''].join(' ') }), sum.busy ? t('leader_busy') : t('leader_idle_float'))),
      h('button', { type: 'button', onClick: onClose, 'aria-label': t('collapse'), title: t('collapse'), style: { marginLeft: 'auto', border: 0, background: T.bg2, width: 32, height: 32, borderRadius: 9999, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: T.text } }, h(Icon, { name: 'x', size: 16 }))),
    h('div', { className: 'bd' }, h(LeaderChat, {})))
}

// ─────────────────────────────────────────────────────────────────────────────
// Trip switcher
// ─────────────────────────────────────────────────────────────────────────────

export function TripSwitcher({ trips, current, onPick, variant, hidden = 0 }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useClickAway(ref, useCallback(() => setOpen(false), []), open)
  const cur = trips.find((tr) => String(tr.id) === String(current)) || null
  const badge = (tr) => (tr && tr.day_count ? t('days_badge', { n: tr.day_count }) : t('trip_fallback'))
  const list = h('div', { className: 'td-float td-switch-list' },
    h('div', { className: 'td-menu-head' }, t('switch_trips', { n: trips.length })),
    ...trips.map((tr) => h('button', {
      key: tr.id, type: 'button', className: ['td-switch-row', String(tr.id) === String(current) ? 'on' : ''].join(' '),
      onClick: () => { onPick(String(tr.id)); setOpen(false) },
    },
    h('span', { className: 'td-switch-badge' }, badge(tr)),
    h('span', { style: { minWidth: 0 } },
      h('div', { className: 't' }, tr.title || t('trip_num', { id: tr.id })),
      h('div', { className: 's' }, [fmtRange(tr.start_date, tr.end_date), tr.place_count ? t('places_n', { n: tr.place_count }) : ''].filter(Boolean).join(' · '))),
    String(tr.id) === String(current) ? h(Icon, { name: 'check', size: 16, style: { marginLeft: 'auto' } }) : null)),
    hidden > 0 ? h('div', { className: 'td-menu-head', style: { borderTop: `1px solid ${T.line2}`, marginTop: 4, paddingTop: 10 } }, t('hidden_trips', { n: hidden })) : null)

  if (variant === 'map') {
    return h('div', { ref, className: 'td-switch' },
      h('button', { type: 'button', className: 'td-float td-trip-pill', onClick: () => setOpen((v) => !v) },
        h('span', { className: 'td-switch-badge' }, badge(cur)),
        h('span', { style: { minWidth: 0 } },
          h('div', { className: 't' }, cur ? cur.title : t('pick_trip')),
          h('div', { className: 's' }, cur ? fmtRange(cur.start_date, cur.end_date) : '')),
        h('span', { className: 'td-switch-hint', style: { marginLeft: 'auto' } }, t('switch'), h(Icon, { name: 'chevron', size: 14 }))),
      open ? list : null)
  }
  return h('div', { ref, className: 'td-switch' },
    h('button', { type: 'button', className: 'td-switch-btn', onClick: () => setOpen((v) => !v), title: t('switch_title') },
      h('span', { className: 'td-switch-badge' }, badge(cur)),
      h('span', { className: 'td-switch-title' }, cur ? cur.title : t('pick_trip')),
      h('span', { className: 'td-switch-hint' }, trips.length > 1 ? t('switch_n', { n: trips.length }) : t('switch'), h(Icon, { name: 'chevron', size: 14 }))),
    open ? list : null)
}

// ─────────────────────────────────────────────────────────────────────────────
// Overflow menu — everyday actions + the door to Settings
// ─────────────────────────────────────────────────────────────────────────────

export function MoreMenu({ trekUrl, onRefresh, onToast, onOpenSettings }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useClickAway(ref, useCallback(() => setOpen(false), []), open)

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(localizeHost(trekUrl))
      onToast && onToast(t('link_copied'))
    } catch (err) {
      onToast && onToast(t('copy_failed'))
    }
    setOpen(false)
  }

  return h('div', { ref, style: { position: 'relative' } },
    h(IconButton, { name: 'more', title: t('more'), onClick: () => setOpen((v) => !v) }),
    open ? h('div', { className: 'td-float td-menu' },
      h('button', { type: 'button', className: 'td-menu-item', onClick: () => { setOpen(false); onRefresh && onRefresh() } }, h(Icon, { name: 'refresh', size: 16 }), t('menu_refresh')),
      trekUrl ? h('a', { className: 'td-menu-item', href: localizeHost(trekUrl), target: '_blank', rel: 'noreferrer', title: t('open_full_title') }, h(Icon, { name: 'external', size: 16 }), t('menu_open_full')) : null,
      trekUrl ? h('button', { type: 'button', className: 'td-menu-item', onClick: copyLink }, h(Icon, { name: 'copy', size: 16 }), t('menu_copy_link')) : null,
      onOpenSettings ? h('div', { className: 'td-menu-sep' }) : null,
      onOpenSettings ? h('button', { type: 'button', className: 'td-menu-item', onClick: () => { setOpen(false); onOpenSettings() } }, h(Icon, { name: 'gear', size: 16 }), t('menu_settings')) : null,
    ) : null)
}

export { Pill }
