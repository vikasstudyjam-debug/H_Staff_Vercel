import React from 'react';
import { tr } from '../i18n.js';

export default function LandingHero({
  onLoginClick,
  onGetStartedClick,
  onDemoClick,
  language = 'en',
  setLanguage = () => {},
}) {
  const t = (k) => tr(language, k);

  return (
    <div className="hstaff-landing hstaff-marketplace-landing" id="top">
      <div className="hstaff-landing-beams" />
      <header className="hstaff-landing-nav">
        <a href="#top" className="hstaff-landing-brand" aria-label="H-Staff home">
          <div className="hstaff-landing-brand-icon">H</div>
          <span>H-Staff</span>
        </a>

        <nav className="hstaff-landing-pill" aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#services">Services</a>
          <button type="button" onClick={onDemoClick}>Demo</button>
          <button type="button" onClick={onLoginClick}>Admin</button>
        </nav>

        <div className="hstaff-landing-actions">
          <select
            className="hstaff-landing-lang"
            aria-label={t('Language')}
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value);
              localStorage.setItem('hstaff_language', e.target.value);
            }}
          >
            <option value="en">EN</option>
            <option value="hi">हिन्दी</option>
            <option value="mr">मराठी</option>
          </select>
          <button type="button" className="hstaff-landing-signin" onClick={onLoginClick}>
            {t('Sign in')}
          </button>
          <button type="button" className="hstaff-btn-white" onClick={onGetStartedClick}>
            Get started
          </button>
        </div>
      </header>

      <main className="hstaff-market-hero">
        <section className="hstaff-market-copy">
          <div className="hstaff-landing-eyebrow">
            <span className="hstaff-landing-dot" />
            <span>STAFFING • SHIFT MANAGEMENT • WORKER MARKETPLACE</span>
          </div>
          <h1 className="hstaff-market-title">
            Find the right workers. <span>Get the work done.</span>
          </h1>
          <p className="hstaff-market-subtitle">
            H-Staff helps customers find and manage workers for scheduled shifts and on-demand jobs.
            Create a request, connect with available workers, and manage each job from one place.
          </p>
          <div className="hstaff-landing-cta-row">
            <button type="button" className="hstaff-btn-white" onClick={onGetStartedClick}>
              Find workers <span aria-hidden="true">→</span>
            </button>
            <button type="button" className="hstaff-btn-outline" onClick={onDemoClick}>
              Explore the demo
            </button>
          </div>
          <p className="hstaff-market-note">
            Need to manage your workforce? <button type="button" onClick={onLoginClick}>Sign in to your account</button>
          </p>

          <div className="hstaff-market-benefits">
            <div><span>✓</span> Create scheduled shifts</div>
            <div><span>✓</span> Request workers on demand</div>
            <div><span>✓</span> Track active job progress</div>
            <div><span>✓</span> Verify job completion with OTP</div>
          </div>

          <div className="hstaff-market-help">
            <div className="hstaff-market-help-icon">HS</div>
            <div>
              <strong>One platform for workforce operations</strong>
              <p>Customer tools, worker access and admin controls in one connected system.</p>
            </div>
          </div>
        </section>

        <section className="hstaff-market-visual" aria-label="H-Staff platform preview">
          <div className="hstaff-market-orbit hstaff-market-orbit-one" />
          <div className="hstaff-market-orbit hstaff-market-orbit-two" />
          <div className="hstaff-product-window">
            <aside className="hstaff-product-sidebar">
              <div className="hstaff-product-brand"><span>H</span> H-Staff</div>
              <div className="hstaff-product-nav active">Overview</div>
              <div className="hstaff-product-nav">Find Workers</div>
              <div className="hstaff-product-nav">My Shifts</div>
              <div className="hstaff-product-nav">On-Demand Jobs</div>
              <div className="hstaff-product-nav">Payments</div>
            </aside>
            <div className="hstaff-product-content">
              <div className="hstaff-product-topline">
                <div><small>CUSTOMER WORKSPACE</small><strong>Workforce overview</strong></div>
                <span className="hstaff-product-avatar">U</span>
              </div>
              <div className="hstaff-product-welcome">
                <div><small>YOUR WORK, ORGANIZED</small><strong>Manage jobs with confidence.</strong><p>Keep requests, workers and shift updates together.</p></div>
                <span className="hstaff-product-welcome-icon">✦</span>
              </div>
              <div className="hstaff-product-cards">
                <div><span className="hstaff-product-card-icon purple">＋</span><strong>Create a shift</strong><small>Schedule workers in advance</small></div>
                <div><span className="hstaff-product-card-icon blue">⌖</span><strong>Find workers</strong><small>Browse available manpower</small></div>
                <div><span className="hstaff-product-card-icon green">↗</span><strong>Request help now</strong><small>Post an on-demand job</small></div>
              </div>
              <div className="hstaff-product-activity">
                <div className="hstaff-product-activity-head"><strong>Job activity</strong><span>Illustrative preview</span></div>
                <div className="hstaff-product-job"><span className="hstaff-job-dot purple-dot" /><div><strong>Scheduled shift</strong><small>Review assigned workers and shift details</small></div><b>Manage</b></div>
                <div className="hstaff-product-job"><span className="hstaff-job-dot green-dot" /><div><strong>Active job</strong><small>Follow worker progress and completion</small></div><b>Track</b></div>
              </div>
            </div>
          </div>
          <div className="hstaff-worker-preview">
            <div className="hstaff-worker-preview-notch" />
            <div className="hstaff-worker-preview-label">WORKER ACCESS</div>
            <strong>New job details</strong>
            <p>View the job and respond to the request.</p>
            <div className="hstaff-worker-preview-button">View job</div>
          </div>
          <div className="hstaff-market-floating-tag"><span>✓</span> Job completion verification</div>
        </section>
      </main>

      <section className="hstaff-market-how" id="how-it-works">
        <div className="hstaff-market-section-heading">
          <small>HOW H-STAFF WORKS</small>
          <h2>From worker request to job completion</h2>
          <p>A straightforward workflow for customers, workers and administrators.</p>
        </div>
        <div className="hstaff-market-steps">
          <article><span>01</span><h3>Create a request</h3><p>Set up a scheduled shift or post an on-demand worker requirement.</p></article>
          <article><span>02</span><h3>Connect with workers</h3><p>Review worker details and manage applications or assignments.</p></article>
          <article><span>03</span><h3>Manage the job</h3><p>Follow active work, verify arrival and confirm completion.</p></article>
        </div>
      </section>

      <section className="hstaff-market-services" id="services">
        <div><small>BUILT AROUND YOUR WORKFLOW</small><h2>Everything in one workforce platform</h2></div>
        <div className="hstaff-market-service-grid">
          <article><span>⌕</span><h3>Worker marketplace</h3><p>Discover and connect with workers for your requirements.</p></article>
          <article><span>▦</span><h3>Shift management</h3><p>Create, organize and manage scheduled work shifts.</p></article>
          <article><span>⚡</span><h3>On-demand staffing</h3><p>Post urgent job requirements and manage responses.</p></article>
          <article><span>⌖</span><h3>Job tracking</h3><p>Follow assigned work and worker progress during active jobs.</p></article>
          <article><span>✓</span><h3>OTP verification</h3><p>Use verification steps for job arrival and completion.</p></article>
          <article><span>▤</span><h3>Admin management</h3><p>Manage users, worker records, operations and platform activity.</p></article>
        </div>
      </section>

      <footer className="hstaff-market-footer">
        <div className="hstaff-landing-brand"><div className="hstaff-landing-brand-icon">H</div><span>H-Staff</span></div>
        <span>Workforce management made simpler.</span>
        <button type="button" onClick={onGetStartedClick}>Get started →</button>
      </footer>
    </div>
  );
}
