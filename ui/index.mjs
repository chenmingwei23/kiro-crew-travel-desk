/**
 * 旅行规划 (Travel Desk) — KiroCrew app UI, v2.
 *
 * An Airbnb-style trip page (hero, day-by-day timeline with photos, sticky
 * leader chat) with a full-screen map view (pins + photo card rail). The UI
 * reads TREK through this app's own backend — nothing is iframed, so it needs
 * no second port and renders wherever the dashboard renders.
 *
 * Files: theme.mjs (tokens/styles/icons), data.mjs (API + derived data +
 * hooks), map.mjs (Leaflet), parts.mjs (chat/switcher/menu), trip.mjs (page),
 * mapview.mjs (map view).
 */

import { createElement as h, useState, useEffect, useRef, useCallback } from 'react'
import { injectStyles, Pill, Icon } from './theme.mjs'
import { getJSON, usePoll, readPref, writePref, PREF } from './data.mjs'
import { TripPage, EmptyState, Workbench } from './trip.mjs'
import { MapView } from './mapview.mjs'
import { SettingsPage } from './settings.mjs'
import { ConnectPage } from './setup.mjs'
import { t, useLang } from './i18n.mjs'

injectStyles()

function newestId(trips) {
  return trips.reduce((m, tr) => (Number(tr.id) > m ? Number(tr.id) : m), -Infinity)
}

/**
 * The language a trip was WRITTEN in, from its title's script. The crew writes
 * a whole trip in the language of the request, so the title decides: any CJK
 * character means 中文, otherwise English. The interface shows the trips of its
 * own language -- an English screen never carries a Chinese headline.
 */
export function tripLang(trip) {
  return /[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]/.test(String((trip && trip.title) || '')) ? 'zh-CN' : 'en'
}

export default function TravelDesk() {
  const lang = useLang() // a language switch re-renders the whole tree; every label reads t() at render
  const [trips, tripsError, reloadTrips] = usePoll(() => getJSON('/trips'), 20000, [])
  const [status, , reloadStatus] = usePoll(() => getJSON('/status'), 20000, [])
  const [org] = usePoll(() => getJSON('/org'), 10000, [])
  const [currentId, setCurrentId] = useState(() => readPref(PREF.trip, null))
  const [view, setView] = useState(null)
  const [viewError, setViewError] = useState('')
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState(() => (readPref(PREF.view, 'trip') === 'map' ? 'map' : 'trip'))
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [bench, setBench] = useState(() => readPref(PREF.bench, '') === '1') // chat fills the page
  const [mapDay, setMapDay] = useState(null)
  const [mapSelected, setMapSelected] = useState(null)
  const [toast, setToast] = useState('')
  const userPicked = useRef(!!readPref(PREF.trip, null))
  const seenNewest = useRef(new Map()) // per language: newest trip id already seen
  const photosAsked = useRef(new Map())
  const toastTimer = useRef(null)

  const allTrips = (trips && Array.isArray(trips.trips)) ? trips.trips : []
  const tripList = allTrips.filter((tr) => tripLang(tr) === lang)
  const hiddenTrips = allTrips.length - tripList.length
  const members = (org && Array.isArray(org.members)) ? org.members : []

  const showToast = useCallback((text) => {
    setToast(text)
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(''), 2600)
  }, [])

  // Pick a trip: remembered one if it still exists, else the newest. Follow new
  // trips the crew writes while the user has not chosen one by hand. All within
  // the interface language; a switch re-picks immediately.
  useEffect(() => {
    if (!trips) return
    if (!tripList.length) { setCurrentId(null); setView(null); setLoading(false); return }
    const ids = tripList.map((tr) => String(tr.id))
    const newest = newestId(tripList)
    const seen = seenNewest.current.get(lang)
    if (seen != null && newest > seen && !userPicked.current) {
      const tr = tripList.find((x) => Number(x.id) === newest)
      setCurrentId(String(newest))
      if (tr) showToast(t('new_trip_toast', { title: tr.title }))
    } else if (currentId == null || !ids.includes(String(currentId))) {
      setCurrentId(String(newest))
    }
    seenNewest.current.set(lang, newest)
  }, [trips, lang]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load + poll the current trip.
  const loadView = useCallback(async () => {
    if (currentId == null) return
    try {
      // `lang` rides along so the desk's note of what is on screen names the language too
      const v = await getJSON(`/trip?id=${encodeURIComponent(currentId)}&lang=${encodeURIComponent(lang)}`)
      setView(v); setViewError('')
    } catch (err) {
      setViewError(String((err && err.message) || err))
    } finally {
      setLoading(false)
    }
  }, [currentId, lang])

  useEffect(() => {
    setView(null); setViewError('')
    if (currentId == null) return undefined
    setLoading(true)
    loadView()
    const t = setInterval(loadView, 30000)
    return () => clearInterval(t)
  }, [loadView, currentId])

  // Resolve missing photos: ask once now, then again on later polls while some
  // are still pending (Wikipedia throttles; the backend paces itself). Bounded.
  useEffect(() => {
    if (!view || !view.photos_pending || !view.trip) return
    const key = String(view.trip.id)
    const rec = photosAsked.current.get(key) || { n: 0, at: 0 }
    if (rec.n >= 6 || Date.now() - rec.at < 25000) return
    photosAsked.current.set(key, { n: rec.n + 1, at: Date.now() })
    getJSON(`/photos?id=${encodeURIComponent(key)}`).then((res) => {
      const photos = (res && res.photos) || {}
      setView((cur) => {
        if (!cur || String(cur.trip.id) !== key) return cur
        const places = { ...cur.places }
        for (const pid of Object.keys(places)) {
          if (photos[pid]) places[pid] = { ...places[pid], photo: photos[pid] }
        }
        const stays = (cur.stays || []).map((s) => (photos[String(s.place_id)] ? { ...s, photo: photos[String(s.place_id)] } : s))
        let cover = cur.trip.cover_place_id
        if (cover == null) {
          const first = Object.values(places).find((p) => p.photo)
          cover = first ? first.id : null
        }
        const pending = typeof res.pending === 'number' ? res.pending : 0
        return { ...cur, places, stays, photos_pending: pending, trip: { ...cur.trip, cover_place_id: cover } }
      })
    }).catch(() => { /* photos are decoration; the page stands without them */ })
  }, [view]) // eslint-disable-line react-hooks/exhaustive-deps

  const onPickTrip = useCallback((id) => {
    userPicked.current = true
    writePref(PREF.trip, id)
    setCurrentId(String(id))
    setMapDay(null); setMapSelected(null)
  }, [])

  const onRefresh = useCallback(() => { reloadTrips(); reloadStatus(); loadView() }, [reloadTrips, reloadStatus, loadView])

  const showMap = useCallback((day, selectedId) => {
    setMapDay(day == null ? null : day)
    setMapSelected(selectedId == null ? null : String(selectedId))
    setMode('map'); writePref(PREF.view, 'map')
  }, [])
  const showTrip = useCallback(() => { setMode('trip'); writePref(PREF.view, 'trip') }, [])
  const openBench = useCallback(() => { setBench(true); writePref(PREF.bench, '1') }, [])
  const closeBench = useCallback(() => { setBench(false); writePref(PREF.bench, '') }, [])

  const noTrips = !!trips && tripList.length === 0
  // The backend connects on its own when it can (login on file, a planner already
  // in local Docker, a valid ticket). Only while none of that holds is there
  // nothing to show, and the page offers the one-click run + the Settings row.
  const notConnected = !!(status && status.setup_needed)
  const openSettings = useCallback(() => setSettingsOpen(true), [])
  const closeSettings = useCallback(() => setSettingsOpen(false), [])
  const onConnected = useCallback(() => { reloadStatus(); reloadTrips() }, [reloadStatus, reloadTrips])
  const common = { trips: tripList, hiddenTrips, currentId, onPickTrip, members, status, onRefresh, onToast: showToast, onOpenSettings: openSettings }

  let body
  if (settingsOpen) {
    body = h(SettingsPage, { status, members, onBack: closeSettings, onRefresh, onToast: showToast })
  } else if (notConnected) {
    body = h(ConnectPage, { status, onOpenSettings: openSettings, onDone: onConnected })
  } else if (mode === 'map' && !noTrips) {
    body = h(MapView, { ...common, view, initialDay: mapDay, initialSelected: mapSelected, onBack: showTrip })
  } else if (bench) {
    body = h(Workbench, { ...common, view: noTrips ? null : view, onShowMap: showMap, onCloseBench: closeBench })
  } else if (noTrips) {
    body = h(EmptyState, { ...common, onOpenBench: openBench })
  } else {
    body = h(TripPage, { ...common, view, onShowMap: showMap, onOpenBench: openBench, loading, error: viewError || (trips && trips.error) || tripsError })
  }

  return h('div', { className: 'td-root' },
    body,
    !settingsOpen && !notConnected && !noTrips && !bench && mode === 'trip' && view ? h(Pill, { dark: true, className: 'td-showmap', onClick: () => showMap(null, null) }, h(Icon, { name: 'map', size: 18 }), t('see_map')) : null,
    toast ? h('div', { className: 'td-toast', role: 'status' }, toast) : null)
}
