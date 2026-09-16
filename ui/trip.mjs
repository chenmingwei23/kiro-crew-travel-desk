/**
 * trip.mjs — the editorial trip page (design B): hero photo, "about" facts,
 * one block per day (notes, timeline of stops and cards, the night's stay, a
 * small "today" map) and the sticky leader-chat card on the right.
 */

import { createElement as h, useState } from 'react'
import { Icon, Pill, Photo, Legend, T } from './theme.mjs'
import { TripMap } from './map.mjs'
import { ChatCard, TripSwitcher, MoreMenu } from './parts.mjs'
import {
  fmtRange, fmtMD, weekday, daysUntil, timeRange, dayStops, staysForDay, dayFromTo, heroUrl, localizeHost,
  sendToLeader, shortName,
} from './data.mjs'
import { t } from './i18n.mjs'

const TRANSPORT_KEY = { driving: 'tr_driving', walking: 'tr_walking', transit: 'tr_transit', cycling: 'tr_cycling', flying: 'tr_flying', train: 'tr_train' }

function transportLabel(view) {
  const modes = (view.days || []).map((d) => d.transport).filter(Boolean)
  const mode = modes.sort((a, b) => modes.filter((m) => m === b).length - modes.filter((m) => m === a).length)[0]
  return TRANSPORT_KEY[mode] ? t(TRANSPORT_KEY[mode]) : ''
}

function countdown(view) {
  const n = daysUntil(view.trip.start)
  if (n == null) return ''
  if (n > 1) return t('cd_days', { n })
  if (n === 1) return t('cd_tomorrow')
  if (n === 0) return t('cd_today')
  const m = daysUntil(view.trip.end)
  if (m != null && m >= 0) return t('cd_ongoing')
  return t('cd_over')
}

// ─────────────────────────────────────────────────────────────────────────────
// Top bar + hero
// ─────────────────────────────────────────────────────────────────────────────

export function TopBar({ trips, hiddenTrips, currentId, onPickTrip, trekUrl, onRefresh, onShowMap, onToast, onOpenSettings, hideMap }) {
  return h('div', { className: 'td-topbar' },
    h('div', { className: 'td-brand' }, h(Icon, { name: 'pin', size: 22, stroke: 2.2 }), t('brand')),
    trips.length ? h(TripSwitcher, { trips, current: currentId, onPick: onPickTrip, hidden: hiddenTrips }) : null,
    h('div', { style: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 } },
      !hideMap && onShowMap ? h(Pill, { onClick: () => onShowMap(null, null), title: t('see_map_title') }, h(Icon, { name: 'map', size: 16 }), t('see_map')) : null,
      h(MoreMenu, { trekUrl, onRefresh, onToast, onOpenSettings })))
}

function Hero({ view, onToast }) {
  const src = heroUrl(view)
  const trip = view.trip
  const stops = view.totals ? view.totals.stops : 0
  const meta = [
    fmtRange(trip.start, trip.end),
    t('days_nights', { d: trip.days, n: trip.nights || 0 }),
    transportLabel(view),
    stops ? t('stops_n', { n: stops }) : '',
    countdown(view),
  ].filter(Boolean)
  const url = localizeHost(trip.url)
  async function share() {
    try {
      await navigator.clipboard.writeText(url)
      onToast(t('link_copied'))
    } catch (err) {
      onToast(t('copy_failed_hint'))
    }
  }
  return h('div', { className: 'td-hero', style: src ? null : { background: 'linear-gradient(135deg, #FFB6C1 0%, #FF385C 55%, #B0004E 100%)' } },
    src ? h('img', { src, alt: '' }) : null,
    h('div', { className: 'grad' }),
    h('div', { className: 'actions' },
      h(Pill, { onClick: share }, h(Icon, { name: 'share', size: 16 }), t('share')),
      h('a', { className: 'td-pill', href: url, target: '_blank', rel: 'noreferrer', style: { textDecoration: 'none' }, title: t('open_full_title') }, h(Icon, { name: 'external', size: 16 }), t('menu_open_full'))),
    h('div', { className: 'copy' },
      h('h1', null, trip.title || t('untitled')),
      h('div', { className: 'meta' }, ...meta.flatMap((m, i) => (i ? [h('span', { key: `s${i}`, className: 'sep' }), h('span', { key: i }, m)] : [h('span', { key: i }, m)])))))
}

// ─────────────────────────────────────────────────────────────────────────────
// About + facts
// ─────────────────────────────────────────────────────────────────────────────

function Fact({ icon, title, sub }) {
  return h('div', { className: 'td-fact' },
    h('span', { className: 'ic' }, h(Icon, { name: icon, size: 20 })),
    h('div', null, h('div', { className: 't' }, title), sub ? h('div', { className: 's' }, sub) : null))
}

function About({ view }) {
  const [more, setMore] = useState(false)
  const trip = view.trip
  const desc = trip.description || ''
  const long = desc.length > 150
  const stays = view.stays || []
  const transport = transportLabel(view)
  const facts = [
    { icon: 'calendar', title: t('days_nights', { d: trip.days, n: trip.nights || 0 }), sub: fmtRange(trip.start, trip.end) },
    { icon: 'car', title: t('stops_n', { n: view.totals.stops }), sub: transport ? t('transport_by_day', { t: transport }) : t('by_day') },
    stays.length
      ? { icon: 'bed', title: t('stays_n', { n: stays.length }), sub: stays.map((s) => shortName(s.name)).slice(0, 2).join(' · ') }
      : { icon: 'ticket', title: view.totals.cost ? t('tickets_about', { cur: trip.currency || '', cost: view.totals.cost }) : t('tickets_tbd'), sub: view.totals.cost ? t('tickets_sum') : t('tickets_later') },
  ]
  return h('section', null,
    h('h2', { className: 'td-h2' }, t('about')),
    desc ? h('p', { className: ['td-desc', long && !more ? 'clamp' : ''].join(' ') }, desc) : h('p', { className: 'td-desc', style: { color: T.muted } }, t('no_desc')),
    long ? h('button', { type: 'button', className: 'td-more', onClick: () => setMore((v) => !v) }, more ? t('show_less') : t('show_more')) : null,
    h('p', { style: { margin: '16px 0 0', fontSize: 14, color: T.muted, lineHeight: 1.6 } }, t('about_ai')),
    h('div', { className: 'td-facts' }, ...facts.map((f, i) => h(Fact, { key: i, ...f }))))
}

// ─────────────────────────────────────────────────────────────────────────────
// Day block
// ─────────────────────────────────────────────────────────────────────────────

function NoteItem({ item }) {
  const text = String(item.text || '')
  // TREK notes often start with the same HH:MM the item carries — do not show it twice.
  const stripped = item.time && text.startsWith(item.time) ? text.slice(item.time.length).replace(/^[\s:：,，-]+/, '') : text
  return h('div', { className: 'td-note' },
    item.time ? h('span', { className: 'tm' }, item.time) : null,
    h('span', null, item.icon ? `${item.icon} ` : '', stripped))
}

function StopItem({ item, place, dayNum, onShowMap }) {
  const price = place.price ? `${place.currency || ''} ${place.price}`.trim() : ''
  return h('div', { className: 'td-stop' },
    h(Photo, { src: place.photo, alt: place.name, num: item.order, seed: place.id, tag: price ? t('ticket_tag', { price }) : null }),
    h('div', { className: 'body' },
      h('div', { className: 'tm' }, timeRange(item.time, item.end) || t('time_tbd')),
      h('div', { className: 'nm' }, place.name),
      place.notes ? h('div', { className: 'nt' }, place.notes) : null,
      h('div', { className: 'ad' },
        h(Icon, { name: 'pin', size: 14 }),
        h('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, place.address || t('addr_tbd')),
        onShowMap && typeof place.lat === 'number' ? h('a', { onClick: () => onShowMap(dayNum, String(place.id)) }, t('see_on_map')) : null)))
}

function StayCard({ stay }) {
  const nights = stay.start_day != null && stay.end_day != null ? Math.max(1, stay.end_day - stay.start_day) : null
  return h('div', { className: 'td-stay' },
    h('span', { className: 'ic' }, stay.photo ? h('img', { src: stay.photo, alt: '' }) : h(Icon, { name: 'bed', size: 22 })),
    h('div', { style: { minWidth: 0, flex: 1 } },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' } },
        h('div', { className: 'nm' }, stay.name),
        nights ? h('span', { className: 'td-chip' }, t('nights_n', { n: nights })) : null),
      stay.address ? h('div', { style: { fontSize: 13, color: T.muted, marginTop: 2 } }, stay.address) : null,
      stay.notes ? h('div', { className: 'nt' }, stay.notes) : null),
    h('div', { className: 'tm' },
      stay.check_in ? h('div', null, t('check_in', { t: stay.check_in })) : null,
      stay.check_out ? h('div', null, t('check_out', { t: stay.check_out })) : null))
}

function DayBlock({ view, day, onShowMap }) {
  const stops = dayStops(view, day)
  const { checkIn, checkOut } = staysForDay(view, day.day)
  const fromTo = dayFromTo(view, day)
  // Weekday from the date so it follows the interface language; the backend's
  // Chinese weekday is only a fallback for an unparseable date.
  const wd = weekday(day.date) || day.weekday
  const places = view.places || {}
  return h('section', null,
    h('div', { className: 'td-day-head' },
      h('span', { className: 'n' }, t('day_n', { n: day.day })),
      h('span', { className: 'd' }, [fmtMD(day.date), wd, day.title || fromTo].filter(Boolean).join(' · '))),
    day.notes ? h('p', { className: 'td-day-notes' }, day.notes) : null,
    checkOut.length ? h('div', { className: 'td-checkout' }, h(Icon, { name: 'bed', size: 14 }), t('checkout_line', { time: checkOut[0].check_out || '', name: checkOut[0].name })) : null,
    h('div', { className: 'td-timeline' },
      ...(day.items || []).map((it, i) => {
        if (it.kind === 'card') return h(NoteItem, { key: `c${i}`, item: it })
        const place = places[String(it.place_id)]
        if (!place) return null
        return h(StopItem, { key: `s${it.place_id}-${i}`, item: it, place, dayNum: day.day, onShowMap })
      }),
      ...checkIn.map((st) => h(StayCard, { key: `stay-${st.place_id}`, stay: st }))),
    stops.length ? h('div', { className: 'td-daymap' },
      h('div', { className: 'lbl' }, h(Icon, { name: 'map', size: 18 }), t('today_where'),
        h(Legend, null),
        onShowMap ? h(Pill, { small: true, onClick: () => onShowMap(day.day, null) }, t('zoom'), h(Icon, { name: 'external', size: 14 })) : null),
      h('div', { className: 'map', onClick: onShowMap ? () => onShowMap(day.day, null) : undefined, style: { cursor: onShowMap ? 'zoom-in' : 'default' } },
        h(TripMap, { view, day: day.day, interactive: false, zoomControl: false, padding: [36, 36, 36, 36] }))) : null)
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export function TripPage({ view, trips, hiddenTrips, currentId, onPickTrip, members, status, onRefresh, onShowMap, onToast, onOpenSettings, loading, error }) {
  const trekUrl = view ? view.trip.url : (status && status.trek && status.trek.url)
  return h('div', { className: 'td-scroll' },
    h(TopBar, { trips, hiddenTrips, currentId, onPickTrip, trekUrl, onRefresh, onShowMap, onToast, onOpenSettings }),
    view ? h(Hero, { view, onToast }) : h('div', { className: 'td-hero', style: { height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.muted, fontSize: 14 } }, error ? t('load_error', { error }) : (loading ? t('loading') : '')),
    view ? h('div', { className: 'td-body' },
      h('div', { className: 'td-main' },
        h(About, { view }),
        ...(view.days || []).flatMap((d) => [h('div', { key: `hr${d.day}`, className: 'td-hr' }), h(DayBlock, { key: `d${d.day}`, view, day: d, onShowMap })])),
      h('div', { className: 'td-chatcol' }, h(ChatCard, { members }))) : null)
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty state — nothing planned yet
// ─────────────────────────────────────────────────────────────────────────────

export function EmptyState({ members, status, onRefresh, onToast, onOpenSettings, trips, hiddenTrips, currentId, onPickTrip }) {
  const [sent, setSent] = useState('')
  const trekUrl = status && status.trek && status.trek.url
  async function pick(text) {
    setSent(text)
    await sendToLeader(text)
    onToast(t('sent_toast'))
  }
  return h('div', { className: 'td-scroll' },
    h(TopBar, { trips: trips || [], hiddenTrips, currentId, onPickTrip, trekUrl, onRefresh, onToast, onOpenSettings, hideMap: true }),
    h('div', { className: 'td-empty' },
      h('h1', null, t('empty_h1')),
      h('p', null, t('empty_p1'), h('br'), t('empty_p2')),
      h('div', { className: 'chips' }, ...t('examples').map((ex) => h(Pill, { key: ex, onClick: () => pick(ex), disabled: !!sent, title: t('send_to_leader') }, ex))),
      h(ChatCard, { members, chips: false, subtitle: t('leader_idle_fresh') }),
      hiddenTrips ? h('p', { style: { marginTop: 18, fontSize: 13, color: T.muted } }, t('hidden_trips', { n: hiddenTrips })) : null))
}
