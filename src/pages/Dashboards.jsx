import React from 'react';
import { api } from '../api.js';
import { money, fmtDate, shiftTime } from '../format.js';
import { Icon, PageIntro, Stat, Panel, Async, useLoad, Pill, Empty } from '../components/ui.jsx';
import { ShiftTable, ShiftCard } from './Shifts.jsx';
import { tr } from '../i18n.js';

const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; };

export default function Dashboard({ user, go, language = 'en' }) {
  const state = useLoad(() => api('/dashboard'), [user.id]);
  return <Async state={state}>{d => user.role === 'business' ? <Business d={d} user={user} go={go} language={language} /> : user.role === 'worker' ? <Worker d={d} user={user} go={go} language={language} /> : <Admin d={d} go={go} />}</Async>;
}

function Business({ d, user, go, language }) {
  const t = key => tr(language, key);
  const s = d.stats, p = d.progress;
  return <div className="customer-workspace">
    <section className="customer-hero">
      <div className="customer-hero-copy">
        <span className="market-kicker">{t('YOUR WORKSPACE')}</span>
        <h2>{t(greeting())}, {user.name.split(' ')[0]}</h2>
        <p>{t('What would you like help with today? Find nearby workers or manage your existing bookings.')}</p>
        <div className="customer-hero-actions">
          <button className="btn primary" onClick={() => go('Nearby Jobs')}><Icon name="search" size={17}/>{t('Find a worker')}</button>
          <button className="btn secondary" onClick={() => go('Create Shift')}><Icon name="plus" size={17}/>{t('Schedule a shift')}</button>
        </div>
      </div>
      <div className="customer-hero-art" aria-hidden="true">
        <div className="customer-art-circle"><Icon name="users" size={48}/></div>
        <span className="customer-art-chip chip-one"><Icon name="check-circle" size={15}/> Trusted workers</span>
        <span className="customer-art-chip chip-two"><Icon name="clock" size={15}/> Flexible hours</span>
      </div>
    </section>

    <section className="customer-metric-row" aria-label="Booking overview">
      <div className="customer-metric"><span className="metric-icon violet"><Icon name="shifts"/></span><div><small>{t('Active bookings')}</small><b>{s.active_shifts}</b><span>{s.need_workers} {t('need workers')}</span></div></div>
      <div className="customer-metric"><span className="metric-icon green"><Icon name="users"/></span><div><small>{t('Workers engaged')}</small><b>{s.total_workers}</b><span>{s.pending_applications} {t('applications waiting')}</span></div></div>
      <div className="customer-metric"><span className="metric-icon amber"><Icon name="clock"/></span><div><small>{t('Timesheets to review')}</small><b>{s.pending_timesheets}</b><span>{t('Review submitted hours')}</span></div></div>
      <div className="customer-metric"><span className="metric-icon blue"><Icon name="rupee"/></span><div><small>{t('Total payments')}</small><b>{money(s.total_payments)}</b><span>{t('All time')}</span></div></div>
    </section>

    <section className="customer-shortcuts">
      <button onClick={() => go('Nearby Jobs')}><span><Icon name="pin"/></span><b>{t('Find nearby help')}</b><small>{t('Browse available workers')}</small><i>→</i></button>
      <button onClick={() => go('My Shifts')}><span><Icon name="shifts"/></span><b>{t('Manage bookings')}</b><small>{t('Check your active shifts')}</small><i>→</i></button>
      <button onClick={() => go('Payments')}><span><Icon name="doc"/></span><b>{t('Payment history')}</b><small>{t('View records and invoices')}</small><i>→</i></button>
    </section>

    <section className="customer-content-grid">
      <Panel className="customer-recent-panel" title={t('Recent bookings')} desc={t('Your latest requests and scheduled shifts.')} right={<button className="text-btn" onClick={() => go('My Shifts')}>{t('View all')} →</button>}>
        {d.recent_shifts.length ? <ShiftTable shifts={d.recent_shifts} showBusiness={false} language={language} /> :
          <div className="market-empty"><Empty icon="shifts" title={t('No bookings yet')} text={t('Your bookings will appear here after you request a worker.')} /><button className="btn primary mini" onClick={() => go('Nearby Jobs')}>{t('Find a worker')}</button></div>}
      </Panel>
      <div className="customer-side-column">
        <Panel title={t('Booking progress')} desc={t('A quick view of your requests.')}>
          <div className="customer-progress-item"><div><span>{t('Workers assigned')}</span><b>{p.filled} / {p.positions}</b></div><div className="progress"><span style={{width:pct(p.filled,p.positions)+'%'}}/></div></div>
          <div className="customer-progress-item"><div><span>{t('Timesheets approved')}</span><b>{p.timesheets_done} / {p.timesheets_total}</b></div><div className="progress"><span style={{width:pct(p.timesheets_done,p.timesheets_total)+'%'}}/></div></div>
        </Panel>
        <Panel title={t('Need help?')} className="customer-help-panel">
          <div className="customer-help-content"><span><Icon name="user"/></span><div><b>{t('We are here to help')}</b><p>{t('Get assistance with bookings, workers or payments.')}</p><button className="text-btn" onClick={() => go('Disputes')}>{t('Contact support')} →</button></div></div>
        </Panel>
      </div>
    </section>
  </div>;
}

function Worker({ d, user, go, language }) {
  const t = key => tr(language, key);
  const s = d.stats;
  return <>
    <section className="market-welcome worker-welcome">
      <div><span className="market-kicker">{t('WORKER OVERVIEW')}</span><h2>{t('Hi')}, {user.name.split(' ')[0]}</h2><p>{t('See nearby work, choose a shift, and track your earnings.')}</p></div>
      <button className="btn primary market-main-action" onClick={() => go('Nearby Jobs')}><Icon name="search" size={17} />{t('Find nearby jobs')}</button>
    </section>
    <div className="stats-grid market-stats-grid">
      <Stat label={t('Available shifts')} value={s.available_shifts} hint={t('Open right now')} icon="search" />
      <Stat label={t('My shifts')} value={s.my_shifts} hint={`${s.upcoming} ${t('confirmed')}`} tone="green" icon="shifts" />
      <Stat label={t('Completed shifts')} value={s.completed_shifts} hint={t('Approved timesheets')} tone="purple" icon="check" />
      <Stat label={t('Total earnings')} value={money(s.total_earnings)} hint={t('Approved + paid')} tone="orange" icon="rupee" />
    </div>
    <Panel className="market-main-panel" title={t('Recommended shifts')} desc={t('Open opportunities you have not applied to.')} right={<button className="text-btn" onClick={() => go('Find Shifts')}>{t('Find more')} →</button>}>
      {d.recommended.length ? <div className="worker-shift-list">{d.recommended.map(sh => <ShiftCard key={sh.id} shift={sh} language={language} action={<button className="btn primary mini" onClick={() => go('Find Shifts')}>{t('View details')}</button>} />)}</div>
        : <div className="market-empty"><Empty icon="search" title={t('Nothing new right now')} text={t('Check back soon — new shifts are posted every day.')} /><button className="btn secondary mini" onClick={() => go('Find Shifts')}>{t('Find more')}</button></div>}
    </Panel>
    <Panel className="info-banner">
      <div className="banner-symbol"><Icon name="doc" /></div>
      <div><b>{d.kyc_status === 'Verified' ? t('Your profile is verified') : t('Complete your KYC to apply for shifts')}</b>
        <p>{d.kyc_status === 'Verified' ? t('You can apply for any open shift.') : t('Upload an identity document. An admin will review it shortly.')}</p></div>
      {d.kyc_status !== 'Verified' ? <button className="btn secondary mini" style={{ marginLeft: 'auto' }} onClick={() => go('KYC Documents')}>{t(d.kyc_status)}</button> : <Pill tone="green">{t('Verified')}</Pill>}
    </Panel>
  </>;
}

function Admin({ d, go }) {
  const s = d.stats;
  const actions = [
    ['Users', 'Manage customer accounts and access.', 'users'], ['Workers', 'Review worker profiles and status.', 'hard-hat'],
    ['KYC Verification', 'Review identity documents.', 'shield-check'], ['Nearby Jobs', 'Monitor live marketplace requests.', 'map-pin'],
    ['Payments', 'Collections and payout records.', 'wallet'], ['Disputes', 'Resolve reported issues.', 'message-square-warning'],
    ['Reports', 'Platform activity and earnings.', 'chart-no-axes-combined'], ['Audit Logs', 'Review important admin actions.', 'scroll-text'],
  ];
  const metrics = [
    ['Total workers',s.total_workers,'Registered profiles','users'],
    ['Customers',s.total_businesses,'Marketplace accounts','user-round'],
    ['Active shifts',s.active_shifts,'Currently in progress','briefcase-business'],
    ['KYC pending',s.pending_kyc,'Waiting for review','shield-check'],
    ['Open disputes',s.open_disputes,'Require attention','flag'],
    ['Pending payments',money(s.pending_payments),'Awaiting collection','wallet'],
  ];
  return <div className="admin-command-center">
    <header className="admin-command-header">
      <div><span className="market-kicker">H-STAFF / ADMINISTRATION</span><h2>Operations overview</h2><p>Monitor platform activity and manage day-to-day operations from one place.</p></div>
      <button className="btn primary" onClick={() => go('Reports')}><Icon name="chart" size={16}/> View reports</button>
    </header>
    <section className="admin-metric-grid">
      {metrics.map(([label,value,hint,icon])=><article className="admin-metric-card" key={label}><div className="admin-metric-top"><span>{label}</span><i><Icon name={icon}/></i></div><strong>{value}</strong><small>{hint}</small></article>)}
    </section>
    <section className="admin-main-grid">
      <div className="admin-primary-column">
        <Panel className="admin-registrations-panel" title="Recent registrations" desc="Latest accounts added to H-Staff." right={<button className="text-btn" onClick={() => go('Users')}>Open directory →</button>}>
          <div className="table-wrap"><table><thead><tr><th>Name</th><th>Account type</th><th>Joined</th><th>Status</th></tr></thead><tbody>
            {d.recent_registrations.map(r=><tr key={r.id}><td><b>{r.name}</b></td><td>{r.role==='business'?'Customer':'Worker'}</td><td>{fmtDate(r.created_at)}</td><td><Pill>{r.status}</Pill></td></tr>)}
          </tbody></table></div>
        </Panel>
        <Panel title="Platform operations" desc="Quick access to the tools you use most.">
          <div className="admin-tool-grid">{actions.map(([label,description,icon])=><button className="admin-tool-card" key={label} onClick={()=>go(label)}><span className="admin-tool-icon"><Icon name={icon}/></span><span className="admin-tool-copy"><b>{label}</b><small>{description}</small></span><i>↗</i></button>)}</div>
        </Panel>
      </div>
      <aside className="admin-side-column">
        <Panel title="Attention required" desc="Items that may need admin action.">
          <button className="admin-attention-row" onClick={()=>go('KYC Verification')}><span className="attention-symbol amber"><Icon name="check"/></span><span><b>KYC reviews</b><small>Pending worker verification</small></span><strong>{s.pending_kyc}</strong></button>
          <button className="admin-attention-row" onClick={()=>go('Disputes')}><span className="attention-symbol red"><Icon name="flag"/></span><span><b>Open disputes</b><small>Customer or worker complaints</small></span><strong>{s.open_disputes}</strong></button>
          <button className="admin-attention-row" onClick={()=>go('Payments')}><span className="attention-symbol blue"><Icon name="rupee"/></span><span><b>Pending collections</b><small>Payment records to review</small></span><strong>{money(s.pending_payments)}</strong></button>
        </Panel>
        <Panel title="Admin shortcuts" className="admin-shortcuts-panel">
          <button onClick={()=>go('Shifts')}><Icon name="shifts"/> Manage all shifts <span>→</span></button>
          <button onClick={()=>go('Workers')}><Icon name="users"/> Worker directory <span>→</span></button>
          <button onClick={()=>go('Settings')}><Icon name="settings"/> Platform settings <span>→</span></button>
          <button onClick={()=>go('Audit Logs')}><Icon name="list"/> Audit history <span>→</span></button>
        </Panel>
      </aside>
    </section>
  </div>;
}
