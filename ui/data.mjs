/**
 * data.mjs — everything that is not pixels: API calls, derived trip data,
 * polling hooks, click-away, and the Leaflet loader.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { t, isEn } from './i18n.mjs'

export const APP = 'travel-desk'
export const API = `/api/apps/${APP}`
export const LEADER_AGENT = 'trip-tour-leader'
const LS_TRIP = 'travel-desk.trip'
const LS_VIEW = 'travel-desk.view'
const LS_BENCH = 'travel-desk.bench' // '1' = the chat fills the page (workbench)

/**
 * The leader conversation is PER LANGUAGE: `travel-desk-leader` (中文) and
 * `travel-desk-leader-en` (English). The crew writes the whole trip in the
 * language of the request, so an English session gets a clean English
 * transcript instead of continuing a Chinese one; switching back finds the
 * Chinese history untouched.
 */
export function leaderSlot() {
  return isEn() ? 'travel-desk-leader-en' : 'travel-desk-leader'
}

export function isLeader(m) { return !!m && (m.id === 'leader' || m.layer === 'lead') }

/**
 * The conversation a member answers in when the guest opens their avatar.
 * The leader keeps its per-language slot. A resident member (planner, risk,
 * briefing) that already has a live session is spoken to THERE, so the guest
 * sees what it is doing; otherwise -- and for every leaf analyst, who has no
 * session between dispatches -- a per-member, per-language slot the gateway
 * creates on the first message (`travel-desk-<id>[-en]`).
 */
export function memberSlot(m) {
  if (!m || isLeader(m)) return leaderSlot()
  if (m.slot_key) return String(m.slot_key)
  return `travel-desk-${m.id}${isEn() ? '-en' : ''}`
}

export function memberAgent(m) {
  return (m && m.agent) || LEADER_AGENT
}

/** Members shown in the workbench rail: the leader, then whoever is doing or has
 *  done something on this trip; everyone else folds into one "standing by" row. */
export function crewActivity(members) {
  const leader = members.find(isLeader) || null
  const active = members.filter((m) => m !== leader && m.state && m.state !== 'idle')
  const standby = members.filter((m) => m !== leader && !active.includes(m))
  return { leader, active, standby }
}

/** A member's title / duty / monogram in the interface language (roster fields *_en). */
export function memberTitle(m) { return (isEn() && m.title_en) || m.title || m.name || '' }
export function memberDuty(m) { return (isEn() && m.duty_en) || m.duty || '' }
export function memberLetter(m) {
  if (isEn() && m.avatar_letter_en) return m.avatar_letter_en
  return m.avatar_letter || (m.title || m.id || '?').slice(0, 1)
}

// ─────────────────────────────────────────────────────────────────────────────
// HTTP
// ─────────────────────────────────────────────────────────────────────────────

export async function getJSON(path) {
  const resp = await fetch(`${API}${path}`, { headers: { Accept: 'application/json' } })
  if (!resp.ok) {
    let msg = `${resp.status}`
    try { const body = await resp.json(); if (body && body.error) msg = body.error } catch (err) { /* plain status */ }
    throw new Error(msg)
  }
  return resp.json()
}

export async function postJSON(path, body) {
  const resp = await fetch(`${API}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
  })
  const data = await resp.json().catch(() => ({}))
  return { ok: resp.ok && data.ok !== false, data }
}

/** Connection settings the setup / settings pages may show (never the password). */
export async function getSetup() {
  return getJSON('/setup')
}

/**
 * Send one message into the leader's slot for the current language.
 *
 * Returns as soon as the gateway has ACCEPTED the message, not when the leader
 * has finished answering: the reply is a server-sent stream that lasts the whole
 * turn (a full plan runs half an hour), and the host embed keeps its composer
 * disabled while the send is pending. The body is drained in the background so
 * the connection is not left half-read.
 *
 * `steer` asks the gateway to hand the text to a turn that is already running
 * (a side question while the team plans) instead of queueing it behind the
 * plan; on an idle slot the flag is ignored and a normal turn starts.
 */
export async function sendToLeader(message) {
  return sendToMember(null, message)
}

/** Same as sendToLeader, into the slot of `member` (null = the leader). */
export async function sendToMember(member, message) {
  try {
    const resp = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, slot: memberSlot(member), agent: memberAgent(member), steer: true }),
    })
    if (resp.body && typeof resp.body.pipeTo === 'function') {
      resp.body.pipeTo(new WritableStream()).catch(() => { /* the stream ends with the turn */ })
    } else {
      resp.text().catch(() => '')
    }
  } catch (err) {
    /* the embed refetches on its own */
  }
}

/** Does this chat slot exist on the gateway yet? (404 until its first message.) */
export async function slotExists(slot) {
  try {
    const resp = await fetch(`/api/chat/slots/${encodeURIComponent(slot)}?limit=1`, { headers: { Accept: 'application/json' } })
    await resp.text().catch(() => '') // drain: an unread body keeps the request in flight
    return resp.ok
  } catch (err) {
    return false
  }
}

/** Rewrite a loopback URL's host to the browser's own host (ssh -L support). */
export function localizeHost(url) {
  if (!url) return url
  try {
    const u = new URL(url)
    if (u.hostname === '127.0.0.1' || u.hostname === 'localhost') u.hostname = window.location.hostname
    return u.toString()
  } catch (err) {
    return url
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Local prefs
// ─────────────────────────────────────────────────────────────────────────────

export function readPref(key, fallback) {
  try { const v = window.localStorage.getItem(key); return v == null ? fallback : v } catch (err) { return fallback }
}
export function writePref(key, value) {
  try { window.localStorage.setItem(key, String(value)) } catch (err) { /* private mode */ }
}
export const PREF = { trip: LS_TRIP, view: LS_VIEW, bench: LS_BENCH }

// ─────────────────────────────────────────────────────────────────────────────
// Dates & names
// ─────────────────────────────────────────────────────────────────────────────

const WEEKDAYS_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const WEEKDAYS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function parseDate(s) {
  if (!s) return null
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
}

/** "10 月 17 日" / "Oct 17" */
export function fmtMD(s) {
  const d = parseDate(s)
  if (!d) return s || ''
  return isEn() ? `${MONTHS_EN[d.getMonth()]} ${d.getDate()}` : `${d.getMonth() + 1} 月 ${d.getDate()} 日`
}

/** "10/17" */
export function fmtShort(s) {
  const d = parseDate(s)
  return d ? `${d.getMonth() + 1}/${d.getDate()}` : (s || '')
}

/** "10 月 17 日 – 19 日" / "Oct 17 – 19"; across months "10 月 30 日 – 11 月 2 日" / "Oct 30 – Nov 2" */
export function fmtRange(a, b) {
  const da = parseDate(a); const db = parseDate(b)
  if (!da) return ''
  if (!db || da.getTime() === db.getTime()) return fmtMD(a)
  if (da.getMonth() === db.getMonth()) return isEn() ? `${fmtMD(a)} – ${db.getDate()}` : `${fmtMD(a)} – ${db.getDate()} 日`
  return `${fmtMD(a)} – ${fmtMD(b)}`
}

export function weekday(s) {
  const d = parseDate(s)
  return d ? (isEn() ? WEEKDAYS_EN : WEEKDAYS_ZH)[d.getDay()] : ''
}

/** Days until the trip starts; negative once it has begun. */
export function daysUntil(s) {
  const d = parseDate(s)
  if (!d) return null
  const now = new Date(); now.setHours(0, 0, 0, 0)
  return Math.round((d.getTime() - now.getTime()) / 86400000)
}

/** "贝尔斯海滩 Bells Beach" -> "贝尔斯海滩" (中文) / "Bells Beach" (English); "Captains at the Bay · Apollo Bay" -> "Apollo Bay". */
export function shortName(name) {
  if (!name) return ''
  const parts = String(name).split('·').map((p) => p.trim()).filter(Boolean)
  const base = parts.length > 1 ? parts[parts.length - 1] : parts[0] || ''
  if (isEn()) {
    const latin = base.replace(/[（(].*$/, '').replace(/[\u4e00-\u9fff（）()·、]+/g, ' ').replace(/\s+/g, ' ').trim()
    if (latin) return latin
  }
  const cjk = base.match(/[\u4e00-\u9fff][\u4e00-\u9fff（）()·、]*/)
  const s = (cjk ? cjk[0] : base).replace(/[（(].*$/, '').trim()
  return s || base
}

/** Town of a stay: text after the last "·", else the address town, else the name. */
export function stayTown(stay) {
  if (!stay) return ''
  const parts = String(stay.name || '').split('·').map((p) => p.trim()).filter(Boolean)
  if (parts.length > 1) return parts[parts.length - 1]
  const addr = String(stay.address || '')
  const m = addr.match(/,\s*([^,]+?)\s+[A-Z]{2,3}\s+\d{3,5}/)
  return m ? m[1] : shortName(stay.name)
}

export function timeRange(a, b) {
  if (a && b) return `${a} – ${b}`
  return a || b || ''
}

// ─────────────────────────────────────────────────────────────────────────────
// Derived trip data
// ─────────────────────────────────────────────────────────────────────────────

/** Stays that START on this day (check-in) and stays that END on it (check-out). */
export function staysForDay(view, dayNum) {
  const stays = (view && view.stays) || []
  return {
    checkIn: stays.filter((s) => s.start_day === dayNum),
    checkOut: stays.filter((s) => s.end_day === dayNum && s.start_day !== dayNum),
  }
}

/** Ordered stops of a day with their place merged in. */
export function dayStops(view, day) {
  const places = (view && view.places) || {}
  return (day.items || [])
    .filter((it) => it.kind === 'stop')
    .map((it) => ({ ...it, place: places[String(it.place_id)] || null }))
    .filter((it) => it.place)
}

/** "墨尔本 → Apollo Bay" style from/to for a day header. */
export function dayFromTo(view, day) {
  const days = view.days || []
  const idx = days.findIndex((d) => d.day === day.day)
  const stops = dayStops(view, day)
  const { checkIn } = staysForDay(view, day.day)
  const prev = idx > 0 ? staysForDay(view, days[idx - 1].day).checkIn : []
  const from = prev.length ? stayTown(prev[0]) : (stops.length ? shortName(stops[0].place.name) : '')
  const to = checkIn.length ? stayTown(checkIn[0]) : (stops.length ? shortName(stops[stops.length - 1].place.name) : '')
  if (!from && !to) return ''
  if (from === to) return from
  return `${from} → ${to}`
}

/** All map points of the trip: stops (with day + order) and stays. */
export function tripPoints(view) {
  const out = []
  if (!view) return out
  for (const day of view.days || []) {
    for (const s of dayStops(view, day)) {
      if (typeof s.place.lat !== 'number' || typeof s.place.lng !== 'number') continue
      out.push({ kind: 'stop', day: day.day, order: s.order, id: s.place.id, lat: s.place.lat, lng: s.place.lng, place: s.place, time: s.time, end: s.end })
    }
  }
  for (const st of view.stays || []) {
    if (typeof st.lat !== 'number' || typeof st.lng !== 'number') continue
    out.push({ kind: 'stay', day: st.start_day, id: `stay-${st.place_id}`, lat: st.lat, lng: st.lng, stay: st })
  }
  return out
}

/** Route of one day: stops in order, then the night's stay. */
export function dayRoute(view, dayNum) {
  const pts = tripPoints(view).filter((p) => p.day === dayNum)
  const stops = pts.filter((p) => p.kind === 'stop').sort((a, b) => a.order - b.order)
  const stays = pts.filter((p) => p.kind === 'stay')
  return [...stops, ...stays].map((p) => [p.lat, p.lng])
}

export function heroUrl(view) {
  if (!view || !view.trip) return null
  const id = view.trip.cover_place_id
  if (id == null) return null
  const p = view.places && view.places[String(id)]
  if (p && p.photo) return p.photo
  const st = (view.stays || []).find((s) => s.place_id === id)
  return st && st.photo ? st.photo : null
}

/** Team summary line for the chat header. */
export function teamSummary(members) {
  if (!members || !members.length) return { online: false, text: t('team_none') }
  const leader = members.find((m) => m.id === 'leader' || m.layer === 'lead') || members[0]
  const working = members.filter((m) => m.state === 'working' && m !== leader)
  const done = members.filter((m) => m.state === 'done')
  const sep = isEn() ? ', ' : '、'
  let text
  if (working.length) text = t('team_working', { names: working.slice(0, 3).map(memberTitle).join(sep), more: working.length > 3 })
  else if (done.length) text = t('team_done', { n: members.length })
  else text = t('team_standby', { n: members.length })
  return {
    online: true,
    working: working.length > 0,
    busy: leader.state === 'working',
    leaderText: leader.state === 'working' ? t('leader_planning') : t('leader_online'),
    text,
    leader,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Hooks
// ─────────────────────────────────────────────────────────────────────────────

/** Poll `fn` every `ms`; returns [value, error, reload]. */
export function usePoll(fn, ms, deps) {
  const [value, setValue] = useState(null)
  const [error, setError] = useState('')
  const alive = useRef(true)
  const load = useCallback(async () => {
    try {
      const v = await fn()
      if (alive.current) { setValue(v); setError('') }
    } catch (err) {
      if (alive.current) setError(String((err && err.message) || err))
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    alive.current = true
    load()
    const t = setInterval(load, ms)
    return () => { alive.current = false; clearInterval(t) }
  }, [load, ms])
  return [value, error, load]
}

export function useClickAway(ref, onAway, active = true) {
  useEffect(() => {
    if (!active) return undefined
    function onDown(e) {
      if (ref.current && !ref.current.contains(e.target)) onAway()
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [ref, onAway, active])
}

// ─────────────────────────────────────────────────────────────────────────────
// Leaflet (loaded once from the CDN the dashboard's CSP already admits)
// ─────────────────────────────────────────────────────────────────────────────

const LEAFLET_JS = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/+esm'
const LEAFLET_CSS = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css'
export const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
export const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

let leafletPromise = null

export function loadLeaflet() {
  if (leafletPromise) return leafletPromise
  if (typeof document !== 'undefined' && !document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = LEAFLET_CSS
    document.head.appendChild(link)
  }
  leafletPromise = import(/* @vite-ignore */ LEAFLET_JS).then((mod) => mod.default || mod.L || mod)
  return leafletPromise
}

export function useLeaflet() {
  const [L, setL] = useState(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let on = true
    loadLeaflet().then((lib) => { if (on) setL(lib) }).catch(() => { if (on) setFailed(true) })
    return () => { on = false }
  }, [])
  return { L, failed }
}
