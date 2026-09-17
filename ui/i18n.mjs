/**
 * i18n.mjs — the app's own labels in 中文 / English, and the language store.
 *
 * Only the chrome is translated: buttons, headings, hints, empty states. Trip
 * CONTENT (place names, notes, day titles) is shown exactly as the crew wrote
 * it into TREK, and the leader answers in the leader's own language — this
 * switch never rewrites either.
 *
 * Usage: `t('key')` / `t('key', { n: 3 })` anywhere at render time; the root
 * component calls `useLang()` once so a switch re-renders the whole tree.
 * Strings live in ONE table per language so a missing key is a one-line fix
 * and the English copy can be reviewed as a whole.
 */

import { useSyncExternalStore } from 'react'

const LS_LANG = 'travel-desk.lang'
export const LANGS = [
  { code: 'zh-CN', label: '中文', hint: '简体中文' },
  { code: 'en', label: 'English', hint: 'English (US)' },
]

/** The browser's own language, mapped to a supported code: zh* -> zh-CN, else en. */
function browserLang() {
  try {
    const nav = (typeof navigator !== 'undefined' && navigator.language) || ''
    return /^zh/i.test(nav) ? 'zh-CN' : 'en'
  } catch (err) {
    return 'en'
  }
}

/** The language shown when the user has not chosen one: follows the browser. */
export const DEFAULT_LANG = browserLang()

function detect() {
  try {
    const v = window.localStorage.getItem(LS_LANG)
    if (v && LANGS.some((l) => l.code === v)) return v
  } catch (err) { /* private mode */ }
  return DEFAULT_LANG
}

let current = typeof window !== 'undefined' ? detect() : DEFAULT_LANG
const subs = new Set()

export function getLang() { return current }
export function isEn() { return current === 'en' }

export function setLang(code) {
  if (!LANGS.some((l) => l.code === code) || code === current) return
  current = code
  try { window.localStorage.setItem(LS_LANG, code) } catch (err) { /* private mode */ }
  for (const fn of subs) fn()
}

function subscribe(fn) { subs.add(fn); return () => subs.delete(fn) }

/** Re-render on language change. Call once at the root. */
export function useLang() {
  return useSyncExternalStore(subscribe, getLang, getLang)
}

const plural = (n, one, many) => (Number(n) === 1 ? one : many)

const STRINGS = {
  'zh-CN': {
    brand: '旅行团',
    see_map: '看地图',
    see_map_title: '整页地图',
    more: '更多',
    menu_refresh: '刷新行程',
    menu_open_full: '打开完整行程页',
    open_full_title: '在行程服务里打开，可编辑、手机也能看',
    menu_copy_link: '复制行程链接',
    menu_settings: '设置',
    link_copied: '行程链接已复制',
    copy_failed: '复制失败',
    copy_failed_hint: '复制失败，请从「打开完整行程页」取链接',

    svc_ok: '行程数据正常',
    svc_down: '行程数据服务已停止',
    svc_adv_note: '高级 · 一般用不到。停止后所有行程暂时读不出来。',
    svc_backup: '备份全部行程数据',
    svc_backup_busy: '备份中…',
    svc_restart: '重启行程数据服务',
    svc_restart_busy: '重启中…',
    svc_start: '启动行程数据服务',
    svc_start_busy: '启动中…',
    svc_stop: '停止行程数据服务',
    svc_stop_busy: '停止中…',
    act_backup: '备份',
    act_restart: '重启',
    act_start: '启动',
    act_stop: '停止',
    act_done: '{label}完成',
    act_failed: '{label}失败：{error}',
    unknown_error: '未知错误',

    setup_h1: '连接你的行程服务',
    setup_lead: '旅行团把每一趟行程都存进一个你自己的行程服务里。先连接一个再开始。',
    setup_run_title: '帮我运行',
    setup_run_desc: '用 Docker 在本机启动一个，几分钟就好。',
    setup_have_title: '连接已有的',
    setup_have_desc: '填地址和管理员账号，连上就行。',
    setup_email: '管理员邮箱',
    setup_password: '密码',
    setup_password_hint: '至少 8 个字符',
    setup_port: '端口',
    setup_address: '地址',
    setup_start: '启动行程服务',
    setup_starting: '正在启动，大约要一分钟…',
    setup_test: '测试连接',
    setup_testing: '测试中…',
    setup_save: '保存',
    setup_saving: '保存中…',
    connect_h1: '准备一个行程服务',
    connect: '连接',
    connecting: '连接中…',
    kept_here: '只存在本机',
    or: '或',
    connect_h1_login: '登录行程服务',
    connect_run: '帮我运行（Docker）',
    run_custom: '自定义账号和端口',
    run_created: '已启动。管理员账号 {email}，密码在 trek.env。',
    setup_no_docker: '这台机器上没有 Docker，用不了这个方式。可以在右边连接已有的行程服务。',
    setup_created: '行程服务已启动，正在打开。',
    setup_create_failed: '没能启动：{error}',
    setup_saved: '已连接，正在打开。',
    setup_reachable_ok: '连接成功，登录通过。',
    setup_unreachable: '连不上 {url}。',
    setup_unauth: '连上了，但邮箱或密码不对。',

    switch_trips: '{n} 趟行程',
    days_badge: '{n} 天',
    trip_fallback: '行程',
    trip_num: '行程 #{id}',
    places_n: '{n} 个地点',
    pick_trip: '选择行程',
    switch: '切换',
    switch_n: '切换 · {n} 趟',
    switch_title: '切换行程',

    leader_title: '团长 · AI 行程管家',
    leader_short: '团长',
    leader_busy: '正在安排行程，稍等',
    leader_idle_card: '想改行程，直接在下面说',
    leader_idle_fresh: '在线 · 说一句去哪，就开始',
    leader_idle_float: '在线 · 想改行程直接说',
    fresh_hello: '你好，我是团长。一句话告诉我：去哪、几号到几号、几个人、自驾还是公交。\n团队会查资料、排日程、过风控，行程和地图就出现在这个页面上。',
    send: '发送',
    collapse: '收起',
    bench_open: '放大对话，看团队工作',
    bench_close: '缩小对话，回到行程',
    bench_hint: '规划时这里更宽敞；有小问题随时问，不必等',
    chat_fab: '和团长聊聊',
    placeholder: '和团长聊聊：去哪、几号到几号、几个人、自驾还是公交…',
    no_embed_title: '这里暂时打不开聊天',
    no_embed_body: '你的 KiroCrew 版本还没有嵌入式聊天。到主聊天里对「团长」说一句行程就行。',

    team_n: '团队 {n} 人',
    team_header: '你的旅行团 · {n} 位 AI 成员',
    team_sub: '各管一段：查资料、排日程、审风险、写简报',
    team_pill: '旅行团 · {n} 人',
    layer_lead: '指挥',
    layer_manage: '管理',
    layer_analyst: '分析',
    layer_debate: '辩论',
    layer_risk: '风控',
    layer_brief: '简报',
    state_working: '正在工作',
    state_done: '已完成',
    state_blocked: '需要你',
    state_idle: '待命',
    team_none: '团队尚未就位',
    team_working: ({ names, more }) => `${names}${more ? ' 等' : ''} 正在工作`,
    team_done: '{n} 人团队 · 上一趟已完成',
    team_standby: '{n} 人团队 · 全员待命',
    leader_planning: '团长正在安排',
    leader_online: '团长在线',
    crew_active: '正在为你忙',
    crew_standby_n: '还有 {n} 位待命',
    crew_standby_hide: '收起待命成员',
    crew_row_hint: '点开，直接和这位成员聊',
    member_back: '回到团长',
    member_fresh_hello: ({ title }) => `你好，我是团队里的${title}。关于这趟行程，我这块的事随时问；要改行程，跟团长说一句就行。`,
    member_placeholder: ({ title }) => `问${title}…`,
    member_busy: '正在忙这趟行程，稍等',
    member_online: '在线',

    days_nights: ({ d, n }) => `${d} 天${n ? ` ${n} 晚` : ''}`,
    stops_n: '{n} 个停留点',
    untitled: '未命名行程',
    share: '分享',
    about: '关于这趟行程',
    no_desc: '团长还没写这趟行程的介绍。',
    show_more: '显示更多',
    show_less: '收起',
    about_ai: '这份行程是你的旅行团（AI）按你的一句话排出来的。想改哪天、换酒店、加景点，直接在右边说。',
    by_day: '按天排好',
    transport_by_day: '{t} · 按天排好',
    stays_n: '{n} 家住宿',
    tickets_about: '门票约 {cur} {cost}',
    tickets_tbd: '门票费用待补',
    tickets_sum: '已填价格的地点之和',
    tickets_later: '团长会在确认后补上',

    tr_driving: '自驾',
    tr_walking: '步行',
    tr_transit: '公交',
    tr_cycling: '骑行',
    tr_flying: '飞行',
    tr_train: '火车',

    cd_days: '还有 {n} 天出发',
    cd_tomorrow: '明天出发',
    cd_today: '今天出发',
    cd_ongoing: '正在旅途中',
    cd_over: '已结束',

    ticket_tag: '门票 {price}',
    time_tbd: '时间待定',
    addr_tbd: '地址待补',
    see_on_map: '在地图上看',
    nights_n: ({ n }) => (n === 1 ? '住 1 晚' : `住 ${n} 晚`),
    check_in: '入住 {t}',
    check_out: '退房 {t}',
    checkout_line: ({ time, name }) => `${time ? `${time} ` : ''}退房 · ${name}`,
    day_n: '第 {n} 天',
    today_where: '今天去哪',
    zoom: '放大看',

    load_error: '行程没读出来：{error}',
    loading: '正在读取行程…',
    new_trip_toast: '团长写好了新行程：{title}',

    empty_h1: '去哪儿？',
    empty_p1: '一句话告诉团长：去哪、几号到几号、几个人、自驾还是公交。',
    empty_p2: '团队会查资料、排日程、过风控，然后行程和地图就出现在这里。',
    send_to_leader: '发给团长',
    sent_toast: '已发给团长，几分钟后行程会出现在这里',
    examples: [
      '10 月 17 到 19 日，墨尔本大洋路 3 天自驾，2 个人',
      '国庆 7 天，杭州出发去青岛玩一圈，一家三口，自驾',
      '12 月底东京 5 天，2 个人，公交，第一次去',
    ],

    all: '全部',
    stay_tag: '住宿',
    stay_inout: '入住 {in} · 退房 {out}',
    back_to_trip: '回到行程',
    back_to_trip_title: '回到行程页',
    full_page: '完整行程页',
    rail_label: '{day} · {n} 站',
    rail_hint: '点卡片，地图会跟着走',
    legend_order: '顺序',
    legend_stay: '过夜',
    pin_stay: '住',
    map_loading: '地图加载中…',
    map_failed: '地图组件没能加载（需要能访问 cdn.jsdelivr.net）',

    settings: '设置',
    back: '返回',
    lang_section: '语言',
    lang_desc: '整个页面跟着语言走：按钮和提示，以及这个语言下规划的行程。团队按你提需求的语言写行程，用英文说，整趟就是英文。每种语言各有一段和团长的对话，互不覆盖。',
    hidden_trips: ({ n }) => `另有 ${n} 趟英文行程。切到 English 就能看到。`,
    svc_section: '行程服务',
    svc_desc: '行程、地点和地图都从这里读。它是一个由你自己运行的行程服务。',
    svc_running: '运行中',
    svc_stopped: '已停止',
    svc_status: '状态',
    svc_url: '地址',
    svc_login: '登录邮箱',
    svc_not_connected: '尚未连接',
    svc_connected: '已连接',
    svc_running_no_login: '在运行，还没登录',
    svc_login_detected: '来自本机 Docker 容器，自动识别',
    svc_login_ticket: '票据会到期，请填登录',
    svc_login_ticket_only: '只有票据',
    svc_connect_existing: '连接已有的行程服务',
    svc_run: '帮我运行一个',
    svc_edit: '修改连接',
    advanced: '高级',
    about_section: '关于',
    about_app: '旅行规划 · 一句话生成行程和地图，由你的 AI 旅行团完成。',
    about_team: '团队 {n} 人 · 数据来自你自己的行程服务 · 界面语言只影响这个页面',
  },

  en: {
    brand: 'Travel Desk',
    see_map: 'Map',
    see_map_title: 'Full-screen map',
    more: 'More',
    menu_refresh: 'Refresh trip',
    menu_open_full: 'Open full itinerary',
    open_full_title: 'Opens the trip planner: editable, works on your phone too',
    menu_copy_link: 'Copy trip link',
    menu_settings: 'Settings',
    link_copied: 'Trip link copied',
    copy_failed: 'Copy failed',
    copy_failed_hint: 'Copy failed — take the link from "Open full itinerary"',

    svc_ok: 'Trip data service running',
    svc_down: 'Trip data service stopped',
    svc_adv_note: 'Advanced — rarely needed. While it is stopped no trip can be read.',
    svc_backup: 'Back up all trip data',
    svc_backup_busy: 'Backing up…',
    svc_restart: 'Restart the trip data service',
    svc_restart_busy: 'Restarting…',
    svc_start: 'Start the trip data service',
    svc_start_busy: 'Starting…',
    svc_stop: 'Stop the trip data service',
    svc_stop_busy: 'Stopping…',
    act_backup: 'Backup',
    act_restart: 'Restart',
    act_start: 'Start',
    act_stop: 'Stop',
    act_done: '{label} done',
    act_failed: '{label} failed: {error}',
    unknown_error: 'unknown error',

    setup_h1: 'Connect your trip planner',
    setup_lead: 'The crew keeps every trip in a self-hosted trip planner you own. Connect one to begin.',
    setup_run_title: 'Run it for me',
    setup_run_desc: 'Start one on this machine with Docker in a few minutes.',
    setup_have_title: 'Connect one I already run',
    setup_have_desc: 'Enter its address and admin login to connect.',
    setup_email: 'Admin email',
    setup_password: 'Password',
    setup_password_hint: 'At least 8 characters',
    setup_port: 'Port',
    setup_address: 'Address',
    setup_start: 'Start the trip planner',
    setup_starting: 'Starting, this can take a minute…',
    setup_test: 'Test connection',
    setup_testing: 'Testing…',
    setup_save: 'Save',
    setup_saving: 'Saving…',
    connect_h1: 'Set up a trip planner',
    connect: 'Connect',
    connecting: 'Connecting…',
    kept_here: 'kept on this machine',
    or: 'or',
    connect_h1_login: 'Sign in to your trip planner',
    connect_run: 'Run it for me (Docker)',
    run_custom: 'Custom login and port',
    run_created: 'Started. Admin login {email}; the password is in trek.env.',
    setup_no_docker: 'Docker is not available here, so this option is off. Connect an existing trip planner instead.',
    setup_created: 'Trip planner started. Opening it now.',
    setup_create_failed: 'Could not start it: {error}',
    setup_saved: 'Connected. Opening it now.',
    setup_reachable_ok: 'Connected and signed in.',
    setup_unreachable: 'Could not reach {url}.',
    setup_unauth: 'Reached it, but the email or password was refused.',

    switch_trips: ({ n }) => `${n} ${plural(n, 'trip', 'trips')}`,
    days_badge: ({ n }) => `${n} ${plural(n, 'day', 'days')}`,
    trip_fallback: 'Trip',
    trip_num: 'Trip #{id}',
    places_n: ({ n }) => `${n} ${plural(n, 'place', 'places')}`,
    pick_trip: 'Pick a trip',
    switch: 'Switch',
    switch_n: ({ n }) => `Switch · ${n} ${plural(n, 'trip', 'trips')}`,
    switch_title: 'Switch trip',

    leader_title: 'AI Tour Leader',
    leader_short: 'Tour Leader',
    leader_busy: 'Planning your trip, one moment',
    leader_idle_card: 'Want changes? Just say so below',
    leader_idle_fresh: 'Online · say where, and we start',
    leader_idle_float: 'Online · say what to change',
    fresh_hello: "Hi, I'm your Tour Leader. Tell me in one sentence: where, which dates, how many people, driving or transit.\nThe crew will research it, schedule it and risk-check it, and the trip and map will appear on this page.",
    send: 'Send',
    collapse: 'Close',
    bench_open: 'Open the workbench: a bigger chat, the team at work',
    bench_close: 'Back to the trip',
    bench_hint: 'Room to plan. Ask a side question any time; no need to wait',
    chat_fab: 'Chat with the leader',
    placeholder: 'Tell the leader: where, which dates, how many people, driving or transit…',
    no_embed_title: 'Chat cannot open here yet',
    no_embed_body: 'This KiroCrew build has no embedded chat. Tell the "Tour Leader" agent about your trip in the main chat instead.',

    team_n: ({ n }) => `${n} on the crew`,
    team_header: 'Your travel crew · {n} AI members',
    team_sub: 'Each owns one step: research, scheduling, risk review, briefing',
    team_pill: 'Crew · {n}',
    layer_lead: 'Lead',
    layer_manage: 'Managing',
    layer_analyst: 'Research',
    layer_debate: 'Debate',
    layer_risk: 'Risk',
    layer_brief: 'Briefing',
    state_working: 'Working',
    state_done: 'Done',
    state_blocked: 'Needs you',
    state_idle: 'Standing by',
    team_none: 'Crew not ready yet',
    team_working: ({ names, more }) => `${names}${more ? ' and others' : ''} working`,
    team_done: '{n}-member crew · last trip done',
    team_standby: '{n}-member crew · all standing by',
    leader_planning: 'Leader is planning',
    leader_online: 'Leader online',
    crew_active: 'On your trip now',
    crew_standby_n: ({ n }) => `${n} more standing by`,
    crew_standby_hide: 'Hide standby members',
    crew_row_hint: 'Open a conversation with this member',
    member_back: 'Back to the leader',
    member_fresh_hello: ({ title }) => `Hi, I'm the ${title} on your crew. Ask me anything in my corner of this trip; to change the plan itself, a word to the leader is all it takes.`,
    member_placeholder: ({ title }) => `Ask the ${title}…`,
    member_busy: 'Busy on your trip, one moment',
    member_online: 'Online',

    days_nights: ({ d, n }) => `${d} ${plural(d, 'day', 'days')}${n ? `, ${n} ${plural(n, 'night', 'nights')}` : ''}`,
    stops_n: ({ n }) => `${n} ${plural(n, 'stop', 'stops')}`,
    untitled: 'Untitled trip',
    share: 'Share',
    about: 'About this trip',
    no_desc: 'The leader has not written an intro for this trip yet.',
    show_more: 'Show more',
    show_less: 'Show less',
    about_ai: 'Your travel crew (AI) planned this from one sentence of yours. To change a day, swap a hotel or add a stop, just say so on the right.',
    by_day: 'Arranged by day',
    transport_by_day: '{t} · arranged by day',
    stays_n: ({ n }) => `${n} ${plural(n, 'stay', 'stays')}`,
    tickets_about: 'Tickets about {cur} {cost}',
    tickets_tbd: 'Ticket costs to come',
    tickets_sum: 'Sum of the places with a price',
    tickets_later: 'The leader fills these in once confirmed',

    tr_driving: 'Driving',
    tr_walking: 'Walking',
    tr_transit: 'Transit',
    tr_cycling: 'Cycling',
    tr_flying: 'Flying',
    tr_train: 'Train',

    cd_days: '{n} days to go',
    cd_tomorrow: 'Leaving tomorrow',
    cd_today: 'Leaving today',
    cd_ongoing: 'On the road',
    cd_over: 'Trip over',

    ticket_tag: 'Ticket {price}',
    time_tbd: 'Time TBD',
    addr_tbd: 'Address to come',
    see_on_map: 'See on map',
    nights_n: ({ n }) => `${n} ${plural(n, 'night', 'nights')}`,
    check_in: 'Check-in {t}',
    check_out: 'Check-out {t}',
    checkout_line: ({ time, name }) => `${time ? `${time} ` : ''}Check out · ${name}`,
    day_n: 'Day {n}',
    today_where: "Today's route",
    zoom: 'Enlarge',

    load_error: 'Could not load the trip: {error}',
    loading: 'Loading trip…',
    new_trip_toast: 'The leader finished a new trip: {title}',

    empty_h1: 'Where to?',
    empty_p1: 'Tell the leader in one sentence: where, which dates, how many people, driving or transit.',
    empty_p2: 'The crew researches, schedules and risk-checks it, then the trip and the map appear here.',
    send_to_leader: 'Send to the leader',
    sent_toast: 'Sent to the leader — the trip shows up here in a few minutes',
    examples: [
      'Oct 17–19, Great Ocean Road from Melbourne, 3 days by car, 2 people',
      'A week in early October, Hangzhou to Qingdao loop, family of three, driving',
      'Tokyo for 5 days in late December, 2 people, public transit, first visit',
    ],

    all: 'All',
    stay_tag: 'Stay',
    stay_inout: 'Check-in {in} · Check-out {out}',
    back_to_trip: 'Back to trip',
    back_to_trip_title: 'Back to the trip page',
    full_page: 'Full itinerary',
    rail_label: ({ day, n }) => `${day} · ${n} ${plural(n, 'stop', 'stops')}`,
    rail_hint: 'Tap a card — the map follows',
    legend_order: 'order',
    legend_stay: 'overnight',
    pin_stay: 'Stay',
    map_loading: 'Loading map…',
    map_failed: 'The map could not load (needs access to cdn.jsdelivr.net)',

    settings: 'Settings',
    back: 'Back',
    lang_section: 'Language',
    lang_desc: 'The whole page follows the language: labels and hints, and the trips planned in that language. The crew writes each trip in the language you ask in, so ask in English and the whole trip is English. Each language keeps its own conversation with the leader.',
    hidden_trips: ({ n }) => `${n} more ${n === 1 ? 'trip is' : 'trips are'} in 中文. Switch the language to see ${n === 1 ? 'it' : 'them'}.`,
    svc_section: 'Trip planner',
    svc_desc: 'Trips, places and the map are read from here: the trip planner you run yourself.',
    svc_running: 'Running',
    svc_stopped: 'Stopped',
    svc_status: 'Status',
    svc_url: 'Address',
    svc_login: 'Login',
    svc_not_connected: 'Not connected',
    svc_connected: 'Connected',
    svc_running_no_login: 'Running, not logged in',
    svc_login_detected: 'Picked up from the local Docker container',
    svc_login_ticket: 'the ticket expires; add the login',
    svc_login_ticket_only: 'Ticket only',
    svc_connect_existing: 'Connect an existing trip planner',
    svc_run: 'Run one for me',
    svc_edit: 'Edit connection',
    advanced: 'Advanced',
    about_section: 'About',
    about_app: 'Travel Desk · one sentence in, a trip and a map out — planned by your AI travel crew.',
    about_team: 'Crew of {n} · data from your own trip planner · the language switch affects this page only',
  },
}

/**
 * Translate `key`. `{name}` placeholders are filled from `vars`; a function
 * entry receives `vars` directly (plurals, composed sentences). Falls back to
 * 中文, then to the key itself, so a missing translation is visible, never a
 * crash.
 */
export function t(key, vars) {
  const table = STRINGS[current] || STRINGS[DEFAULT_LANG]
  let s = table[key]
  if (s == null) s = STRINGS[DEFAULT_LANG][key]
  if (s == null) return key
  if (typeof s === 'function') return s(vars || {})
  if (Array.isArray(s)) return s
  if (vars) s = s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] == null ? '' : String(vars[k])))
  return s
}
