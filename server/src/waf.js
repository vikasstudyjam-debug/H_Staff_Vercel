// Layer-7 request filter ported from the FastAPI backend (app/middlewares/waf.py).
// Inspects the URL path and query string for SQL injection, XSS and path-traversal signatures.
// (Rate limiting and security headers are already handled by express-rate-limit and helmet.)
const SQLI = /(--|union\s+select|\/\*|\*\/|exec\s*\(|drop\s+table|insert\s+into|select\s+.*\s+from)/i;
const XSS = /(<script.*?>|javascript:|onload\s*=|onerror\s*=|eval\s*\()/i;
const TRAVERSAL = /(\.\.\/|\.\.\\|\/etc\/passwd|win\.ini)/i;

export function waf(req, res, next) {
  let path = req.path, query = '';
  try { path = decodeURIComponent(req.path); query = decodeURIComponent(req.originalUrl.split('?')[1] || ''); } catch { /* keep raw */ }
  for (const target of [path, query]) {
    if (!target) continue;
    if (SQLI.test(target)) return res.status(403).json({ error: 'Request blocked: potential SQL injection detected.' });
    if (XSS.test(target)) return res.status(403).json({ error: 'Request blocked: potential cross-site scripting payload detected.' });
    if (TRAVERSAL.test(target)) return res.status(403).json({ error: 'Request blocked: directory traversal sequence detected.' });
  }
  next();
}
