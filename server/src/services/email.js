// KYC status e-mails, ported from the FastAPI backend (notification_service.py).
// Sends through SMTP when SMTP_USER/SMTP_PASSWORD are set; otherwise logs to the console.
import { config } from '../config.js';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export async function sendKycStatusEmail(to, name, status, remarks) {
  if (!to) return false;
  const approved = status === 'approved';
  const subject = `H-Staff KYC Status Update: ${status.toUpperCase()}`;
  const html = `<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:24px">
    <h2 style="color:#1e3a8a">H-Staff Verification Center</h2><p>Hello <b>${esc(name)}</b>,</p>
    <p>Your identity document has been reviewed:</p>
    <div style="background:${approved ? '#ecfdf5' : '#fef2f2'};padding:14px;border-radius:6px">
      <b style="color:${approved ? '#065f46' : '#991b1b'}">STATUS: ${esc(status.toUpperCase())}</b>
      <p style="margin:6px 0 0;color:#4b5563">Remarks: ${esc(remarks || 'Complies with platform regulations.')}</p></div></div>`;
  if (!config.smtpUser || !config.smtpPassword) { console.log(`[email:not-configured] To: ${to} | ${subject}`); return false; }
  try {
    const { default: nodemailer } = await import('nodemailer');
    const t = nodemailer.createTransport({ host: config.smtpHost, port: config.smtpPort, secure: config.smtpPort === 465, auth: { user: config.smtpUser, pass: config.smtpPassword } });
    await t.sendMail({ from: config.smtpFrom, to, subject, html });
    return true;
  } catch (e) { console.error('KYC e-mail delivery failed:', e.message); return false; }
}
