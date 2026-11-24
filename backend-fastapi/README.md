# Legacy FastAPI backend (from "final h4")

Kept for reference from the second developer's track. The React frontend in the project root talks to the
Node API in `../server`, **not** to this service. Features from here that were ported to the Node server:
WAF request filter (`server/src/waf.js`) and KYC status e-mails (`server/src/services/email.js`).

Run standalone: `pip install -r requirements.txt && uvicorn app.main:app --reload` (serves its own simple UI at `/`).
Set JWT_SECRET_KEY / RAZORPAY_* via environment before any real use; the defaults in `app/core/config.py` are placeholders.
