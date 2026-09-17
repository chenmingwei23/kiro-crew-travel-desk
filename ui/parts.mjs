/**
 * parts.mjs — chrome shared by the trip page and the map view: the leader
 * chat (native ChatEmbed re-skinned to this page), the sticky chat card and
 * floating chat window, the team popover, the trip switcher and the overflow
 * menu. Service controls live on the settings page (settings.mjs), never here.
 */

import { createElement as h, useState, useRef, useCallback, useEffect } from 'react'
import { Icon, Pill, IconButton, Avatar, Avatars, T } from './theme.mjs'
import {
  LEADER_AGENT, leaderSlot, slotExists, sendToLeader, sendToMember, memberSlot, memberAgent, isLeader, crewActivity,
  useClickAway, teamSummary, fmtRange, localizeHost, memberTitle, memberDuty,
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
function FreshChat({ slot, member, placeholder, onReady, chips = true }) {
  const [draft, setDraft] = useState('')
  const [sent, setSent] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const leader = !member || isLeader(member)
  const title = leader ? t('leader_short') : memberTitle(member)
  const hello = leader ? t('fresh_hello') : t('member_fresh_hello', { title })
  const busy = leader ? t('leader_busy') : t('member_busy')

  async function send(text) {
    const msg = (text || draft).trim()
    if (!msg || sent) return
    setSent(msg); setDraft('')
    await sendToMember(leader ? null : member, msg)
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
      h('div', { className: 'from' }, title),
      h('div', { className: 'bubble' }, hello),
      sent ? h('div', { className: 'bubble me' }, sent) : null,
      sent ? h('div', { className: 'bubble typing', 'aria-label': busy }, h('i'), h('i'), h('i')) : null),
    !sent && chips && leader ? h('div', { className: 'chips' }, ...t('examples').map((ex) => h(Pill, { key: ex, small: true, onClick: () => send(ex), title: t('send_to_leader') }, h('span', null, ex)))) : null,
    h('form', { onSubmit: (e) => { e.preventDefault(); send() } },
      h('input', { type: 'text', value: draft, disabled: !!sent, placeholder: sent ? busy : (placeholder || (leader ? t('placeholder') : t('member_placeholder', { title }))), onChange: (e) => setDraft(e.target.value), 'aria-label': t('chat_fab') }),
      h('button', { type: 'submit', className: 'send', disabled: !!sent || !draft.trim(), title: t('send'), 'aria-label': t('send') }, h(ArrowUp))))
}

/**
 * The conversation with one crew member: the leader by default, or whoever the
 * guest opened from the roster. Same embed, same send path; only the slot and
 * the agent change (see memberSlot / memberAgent in data.mjs).
 */
export function LeaderChat({ placeholder, chips = true, member = null }) {
  const lang = useLang()
  const leader = !member || isLeader(member)
  const slot = memberSlot(leader ? null : member)
  const agent = memberAgent(leader ? null : member)
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
  if (exists === false) return h(FreshChat, { slot, member: leader ? null : member, placeholder, chips, onReady: () => setExists(true) })
  // `.td-embed` re-declares the dashboard's design tokens so the host chat
  // takes this page's palette and type (see theme.mjs "embedded chat").
  // `onSend` replaces the embed's own POST: that one awaits the whole reply
  // stream, which held the composer shut for as long as the team was planning
  // (see sendToLeader). Ours returns once the message is accepted, and steers a
  // running turn so a side question is answered mid-plan.
  return h('div', { className: 'td-embed' },
    h(sdk.ChatEmbed, {
      key: slot,
      slotKey: slot,
      agent,
      frameless: true,
      startAtBottom: true,
      placeholder: placeholder || (leader ? t('placeholder') : t('member_placeholder', { title: memberTitle(member) })),
      onSend: (msg) => sendToMember(leader ? null : member, msg),
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

/** One roster row. A button when `onPick` is given: it opens that member's
 *  conversation. `selected` marks the member the chat is currently with. */
function TeamRow({ m, onPick, selected }) {
  const body = [
    h(Avatar, { member: m, showState: true }),
    h('div', { style: { minWidth: 0 } },
      h('div', { className: 'n' }, memberTitle(m)),
      h('div', { className: 'd' }, memberDuty(m))),
    h('div', { className: ['st', m.state || ''].join(' ') }, stateText(m.state)),
  ]
  const cls = ['td-team-row', onPick ? 'pick' : '', selected ? 'on' : ''].join(' ')
  if (!onPick) return h('div', { className: cls, title: memberDuty(m) }, ...body)
  return h('button', { type: 'button', className: cls, title: t('crew_row_hint'), 'aria-pressed': !!selected, onClick: () => onPick(m) }, ...body)
}

/** The team grouped by layer, one row per member with their state. Shared by the
 *  popover (trip page) and the standing rail (workbench). */
export function TeamList({ members, onPick, selectedId }) {
  const byLayer = new Map()
  for (const m of members) {
    const k = m.layer || 'other'
    if (!byLayer.has(k)) byLayer.set(k, [])
    byLayer.get(k).push(m)
  }
  const order = LAYERS.map(([k]) => k).concat([...byLayer.keys()].filter((k) => !LAYERS.some(([l]) => l === k)))
  return h('div', { className: 'td-teamlist' },
    ...order.filter((k) => byLayer.has(k)).map((k) => {
      const layer = LAYERS.find(([l]) => l === k)
      return h('div', { key: k },
        h('div', { style: { padding: '8px 6px 2px', fontSize: 11, color: T.muted, letterSpacing: '.04em' } }, layer ? t(layer[1]) : k),
        ...byLayer.get(k).map((m) => h(TeamRow, { key: m.id, m, onPick, selected: selectedId === m.id })))
    }))
}

/**
 * The workbench rail: who matters right now. The leader first, then the
 * members working on (or finished with) this trip, each with what they are
 * doing; the rest fold into one "N more standing by" line that expands to the
 * full roster on request. Every row opens that member's conversation.
 */
export function CrewRail({ members, onPick, selectedId }) {
  const [showAll, setShowAll] = useState(false)
  const { leader, active, standby } = crewActivity(members)
  const rows = []
  if (leader) rows.push(h(TeamRow, { key: leader.id, m: leader, onPick, selected: selectedId === leader.id }))
  if (active.length) {
    rows.push(h('div', { key: 'hd-active', className: 'td-rail-hd' }, t('crew_active')))
    rows.push(...active.map((m) => h(TeamRow, { key: m.id, m, onPick, selected: selectedId === m.id })))
  }
  if (standby.length) {
    rows.push(h('button', { key: 'fold', type: 'button', className: 'td-rail-fold', 'aria-expanded': showAll, onClick: () => setShowAll((v) => !v) },
      h('span', { className: 'td-avatars' }, ...standby.slice(0, 3).map((m) => h(Avatar, { key: m.id, member: m, size: 'sm' }))),
      h('span', null, showAll ? t('crew_standby_hide') : t('crew_standby_n', { n: standby.length })),
      h(Icon, { name: 'chevron', size: 14, style: { marginLeft: 'auto', transform: showAll ? 'rotate(180deg)' : 'none' } })))
    if (showAll) rows.push(h(TeamList, { key: 'all', members: standby, onPick, selectedId }))
  }
  return h('div', { className: 'td-teamlist td-crewrail' }, ...rows)
}

export function TeamPopover({ members, onClose, style, onPick, selectedId }) {
  const ref = useRef(null)
  useClickAway(ref, onClose)
  return h('div', { ref, className: 'td-float td-team', style },
    h('div', { style: { display: 'flex', alignItems: 'center', padding: '4px 6px 10px' } },
      h('div', null,
        h('div', { style: { fontSize: 15, fontWeight: 600 } }, t('team_header', { n: members.length })),
        h('div', { style: { fontSize: 12, color: T.muted, marginTop: 2 } }, t('team_sub'))),
      h('button', { type: 'button', onClick: onClose, 'aria-label': t('collapse'), style: { marginLeft: 'auto', border: 0, background: 'none', cursor: 'pointer', color: T.muted, display: 'inline-flex' } }, h(Icon, { name: 'x', size: 16 }))),
    h(TeamList, { members, onPick, selectedId }))
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat card (trip page, sticky right column)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * `onExpand` adds the workbench button: the chat takes the whole page (see
 * Workbench in trip.mjs). `onShrink` is its counterpart on the workbench's own
 * card. The card talks to the leader unless a member is picked -- from the
 * avatars' popover here, or from the workbench rail through `who`/`onPickWho`
 * (controlled); uncontrolled, it keeps the choice itself.
 */
export function ChatCard({ members, className, chips = true, subtitle, onExpand, onShrink, who, onPickWho }) {
  const [teamOpen, setTeamOpen] = useState(false)
  const [ownWho, setOwnWho] = useState(null)
  const sum = teamSummary(members)
  const pick = onPickWho || setOwnWho
  const picked = (onPickWho ? who : ownWho) || null
  const member = picked && !isLeader(picked) ? (members.find((m) => m.id === picked.id) || picked) : null
  const onPick = (m) => { pick(isLeader(m) ? null : m); setTeamOpen(false) }
  const head = member
    ? [
      h('button', { type: 'button', className: 'td-backleader', onClick: () => pick(null), title: t('member_back'), 'aria-label': t('member_back') }, h(Icon, { name: 'back', size: 16 })),
      h(Avatar, { member, size: 'lg', showState: true }),
      h('div', { className: 'who', style: { flex: 1 } },
        h('div', { className: 't' }, h('span', { className: ['td-online', member.state === 'working' ? 'busy' : ''].join(' ') }), memberTitle(member)),
        h('div', { className: 's' }, member.state === 'working' ? t('member_busy') : memberDuty(member))),
    ]
    : [
      h(Avatars, { members, max: 4, onClick: () => setTeamOpen((v) => !v) }),
      h('div', { className: 'who', style: { flex: 1 } },
        h('div', { className: 't' }, h('span', { className: ['td-online', sum.busy ? 'busy' : ''].join(' ') }), t('leader_title')),
        h('div', { className: 's' }, sum.busy ? t('leader_busy') : (sum.working ? sum.text : (subtitle || t('leader_idle_card'))))),
    ]
  return h('div', { className: ['td-chatcard', className || ''].join(' ') },
    h('div', { className: 'hd', style: { position: 'relative' } },
      ...head,
      onExpand ? h(IconButton, { name: 'expand', size: 16, onClick: onExpand, title: t('bench_open'), className: 'td-benchbtn' }) : null,
      onShrink ? h(IconButton, { name: 'shrink', size: 16, onClick: onShrink, title: t('bench_close'), className: 'td-benchbtn' }) : null,
      teamOpen ? h(TeamPopover, { members, onPick, selectedId: member ? member.id : 'leader', onClose: () => setTeamOpen(false), style: { top: 56, left: 12, right: 12, width: 'auto' } }) : null),
    h('div', { className: 'bd' }, h(LeaderChat, { chips, member })))
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
