import { Router } from 'express';
import crypto from 'node:crypto';
import { z } from 'zod';
import { db, tx } from '../db.js';
import { authenticate, requireRole } from '../auth.js';
import { config } from '../config.js';
import { wrap, bad, forbidden, notFound, conflict, parseId, audit, notify, HttpError, sendSms } from '../util.js';

// On-demand marketplace APIs. Scheduled-shift endpoints remain in shifts.js/attendance.js.
export const router = Router(); router.use(authenticate);
const point=z.object({lat:z.coerce.number().min(-90).max(90),lng:z.coerce.number().min(-180).max(180)});
const dist=(a,b,c,d)=>{const r=x=>x*Math.PI/180,x=r(c-a),y=r(d-b);return 6371000*2*Math.asin(Math.sqrt(Math.sin(x/2)**2+Math.cos(r(a))*Math.cos(r(c))*Math.sin(y/2)**2));};
const hash=(id,code)=>crypto.createHmac('sha256',config.jwtSecret).update(`${id}:${code}`).digest('hex');
const encrypt=(id,code)=>{const key=crypto.createHash('sha256').update(config.jwtSecret).digest(),iv=crypto.randomBytes(12),c=crypto.createCipheriv('aes-256-gcm',key,iv);c.setAAD(Buffer.from(String(id)));const ciphertext=Buffer.concat([c.update(code),c.final()]);return Buffer.concat([iv,c.getAuthTag(),ciphertext]).toString('base64');};
const decrypt=(id,v)=>{const b=Buffer.from(v,'base64'),d=crypto.createDecipheriv('aes-256-gcm',crypto.createHash('sha256').update(config.jwtSecret).digest(),b.subarray(0,12));d.setAAD(Buffer.from(String(id)));d.setAuthTag(b.subarray(12,28));return Buffer.concat([d.update(b.subarray(28)),d.final()]).toString();};
// Start/finish codes: generated when a worker accepts a job. The WORKER sees both codes and hands them to the customer,
// who types the start code to begin the shift and the finish code to end it (which also creates the job payment).
const CODE_TTL_MS=7*24*3600e3;
const newCode=()=>String(crypto.randomInt(100000,1000000));
const sqlTime=ms=>new Date(ms).toISOString().slice(0,19).replace('T',' ');
function putCode(id,purpose,code){const exp=sqlTime(Date.now()+CODE_TTL_MS);db.prepare("INSERT INTO job_verifications(shift_id,purpose,code_hash,code_ciphertext,expires_at,delivery_status) VALUES(?,?,?,?,?,'in_app') ON CONFLICT(shift_id,purpose) DO UPDATE SET code_hash=excluded.code_hash,code_ciphertext=excluded.code_ciphertext,expires_at=excluded.expires_at,attempts=0,consumed_at=NULL,created_at=datetime('now')").run(id,purpose,hash(id,code),encrypt(id,code),exp);}
function issueCodes(id){const a=newCode();let b=newCode();while(b===a)b=newCode();putCode(id,'start',a);putCode(id,'finish',b);db.prepare('UPDATE shifts SET start_otp_hash=? WHERE id=?').run(hash(id,a),id);}
function assignedWorker(id,uid){return db.prepare("SELECT 1 FROM applications WHERE shift_id=? AND worker_id=? AND status='Accepted'").get(id,uid);}
function checkCode(id,purpose,otp){const v=db.prepare("SELECT * FROM job_verifications WHERE shift_id=? AND purpose=?").get(id,purpose);if(!v||v.consumed_at||new Date(`${v.expires_at.replace(' ','T')}Z`).getTime()<=Date.now())throw conflict('This code is no longer valid. Ask the worker for a new code.');if(v.attempts>=5)throw new HttpError(429,'Too many incorrect attempts. Ask the worker to generate a new code.');if(!crypto.timingSafeEqual(Buffer.from(hash(id,otp)),Buffer.from(v.code_hash))){db.prepare('UPDATE job_verifications SET attempts=attempts+1 WHERE id=?').run(v.id);return {invalid:true};}const u=db.prepare("UPDATE job_verifications SET consumed_at=datetime('now'),code_ciphertext=NULL WHERE id=? AND consumed_at IS NULL AND attempts<5").run(v.id);if(!u.changes)throw conflict('Code already used.');return {invalid:false};}

// Amount is fixed when work starts, from the booked time window x hourly rate, so the customer pays BEFORE the shift can be finished.
function bookedAmount(s){const [sh,sm]=s.start_time.split(':').map(Number),[eh,em]=s.end_time.split(':').map(Number);let mins=(eh*60+em)-(sh*60+sm);if(mins<=0)mins+=1440;const hours=Math.max(.25,Math.round(mins/60*4)/4);const amount=Math.max(1,Math.round(hours*s.rate));return {amount,fee:Math.round(amount*config.platformFeePercent/100)};}
function ensureJobPayment(s,workerId){if(db.prepare('SELECT 1 FROM job_payments WHERE shift_id=?').get(s.id))return;const {amount,fee}=bookedAmount(s);db.prepare('INSERT INTO job_payments(shift_id,business_id,worker_id,amount,fee) VALUES(?,?,?,?,?)').run(s.id,s.business_id,workerId,amount,fee);}
const otpBody=z.object({otp:z.string().regex(/^\d{6}$/,'Enter the 6-digit code')});
const job=(id)=>db.prepare("SELECT * FROM shifts WHERE id=? AND job_type='ondemand'").get(id);

router.post('/jobs',requireRole('business'),wrap((req,res)=>{const d=z.object({title:z.string().trim().min(2).max(80),description:z.string().max(1000).optional().default(''),skills:z.array(z.string()).max(10).optional().default([]),location:z.string().trim().min(2).max(160),...point.shape,date:z.string().regex(/^\d{4}-\d{2}-\d{2}$/),start_time:z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/),end_time:z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/),rate:z.coerce.number().int().min(1).max(100000),radius_m:z.coerce.number().int().min(25).max(5000).optional().default(300)}).parse(req.body);if(d.start_time===d.end_time)throw bad('Start and end time must differ');const r=db.prepare("INSERT INTO shifts(business_id,title,description,skills,location,lat,lng,radius_m,date,start_time,end_time,workers_needed,rate,status,job_type) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,'Open','ondemand')").run(req.user.id,d.title,d.description,d.skills.join(','),d.location,d.lat,d.lng,d.radius_m,d.date,d.start_time,d.end_time,d.rate);const near=db.prepare("SELECT u.id,w.lat,w.lng FROM workers w JOIN users u ON u.id=w.user_id WHERE w.available=1 AND w.kyc_status='Verified' AND u.status='Active' AND w.lat IS NOT NULL").all();for(const w of near)if(dist(d.lat,d.lng,w.lat,w.lng)<=d.radius_m)notify(w.id,"A nearby work request is available: "+d.title);audit(req,'ondemand.job_create','shift',r.lastInsertRowid);res.status(201).json({ok:true,job_id:Number(r.lastInsertRowid)});}));

router.post('/workers/location',requireRole('worker'),wrap((req,res)=>{const p=point.extend({available:z.boolean().optional(),accuracy_m:z.coerce.number().min(0).max(10000).optional()}).parse(req.body);const active=db.prepare("SELECT s.id FROM shifts s JOIN applications a ON a.shift_id=s.id WHERE a.worker_id=? AND a.status='Accepted' AND s.job_type='ondemand' AND s.status='Ongoing'").get(req.user.id);if(p.available===true&&active)throw conflict('Complete your active job before becoming available.');db.prepare("UPDATE workers SET lat=?,lng=?,location_accuracy_m=?,location_updated_at=datetime('now'),available=COALESCE(?,available) WHERE user_id=?").run(p.lat,p.lng,p.accuracy_m??null,p.available==null?null:Number(p.available),req.user.id);if(active)db.prepare("INSERT INTO job_locations(shift_id,lat,lng,accuracy_m) VALUES(?,?,?,?) ON CONFLICT(shift_id) DO UPDATE SET lat=excluded.lat,lng=excluded.lng,accuracy_m=excluded.accuracy_m,updated_at=datetime('now')").run(active.id,p.lat,p.lng,p.accuracy_m??null);res.json({ok:true});}));
router.get('/jobs/nearby',requireRole('worker'),wrap((req,res)=>{const p=point.parse(req.query),radius=Math.min(50000,Math.max(100,Number(req.query.radius)||15000));const eligible=db.prepare("SELECT available,kyc_status FROM workers WHERE user_id=?").get(req.user.id);if(!eligible?.available||eligible.kyc_status!=='Verified')return res.json({jobs:[]});const rows=db.prepare("SELECT s.id,s.title,s.description,s.skills,s.location,s.lat,s.lng,s.date,s.start_time,s.end_time,s.rate,s.status,b.company FROM shifts s JOIN businesses b ON b.user_id=s.business_id WHERE s.job_type='ondemand' AND s.status='Open' AND s.lat IS NOT NULL").all().map(j=>({...j,distance_m:Math.round(dist(p.lat,p.lng,j.lat,j.lng))})).filter(j=>j.distance_m<=radius).sort((a,b)=>a.distance_m-b.distance_m);res.json({jobs:rows});}));
router.get('/workers/nearby',requireRole('business','admin'),wrap((req,res)=>{const p=point.parse(req.query),radius=Math.min(50000,Math.max(100,Number(req.query.radius)||10000));const rows=db.prepare("SELECT u.id,u.name,w.skills,w.rating,w.kyc_status,w.lat,w.lng FROM workers w JOIN users u ON u.id=w.user_id WHERE u.status='Active' AND w.kyc_status='Verified' AND w.available=1 AND w.lat IS NOT NULL").all().map(w=>{const distance_m=Math.round(dist(p.lat,p.lng,w.lat,w.lng));const {lat,lng,...safe}=w;return {...safe,distance_m};}).filter(w=>w.distance_m<=radius).sort((a,b)=>a.distance_m-b.distance_m);res.json({workers:rows});}));
router.get('/jobs/mine',requireRole('business','worker','admin'),wrap((req,res)=>{for(const r of db.prepare("SELECT s.*,a.worker_id FROM shifts s JOIN applications a ON a.shift_id=s.id AND a.status='Accepted' WHERE s.job_type='ondemand' AND s.status='Ongoing' AND NOT EXISTS(SELECT 1 FROM job_payments p WHERE p.shift_id=s.id)").all())ensureJobPayment(r,r.worker_id);const where=req.user.role==='business'?'s.business_id=?':req.user.role==='worker'?'a.worker_id=?':'1=1';const rows=db.prepare(`SELECT s.id,s.title,s.location,s.lat,s.lng,s.date,s.start_time,s.end_time,s.rate,s.status,s.business_id,s.completion_requested_at,a.worker_id,u.name worker_name,b.company,jl.lat worker_lat,jl.lng worker_lng,jl.updated_at location_updated,jp.id job_payment_id,jp.amount job_amount,jp.fee job_fee,jp.status job_payment_status,jr.id rating_id,jr.rating,jr.feedback FROM shifts s LEFT JOIN applications a ON a.shift_id=s.id AND a.status='Accepted' LEFT JOIN users u ON u.id=a.worker_id JOIN businesses b ON b.user_id=s.business_id LEFT JOIN job_locations jl ON jl.shift_id=s.id LEFT JOIN job_payments jp ON jp.shift_id=s.id LEFT JOIN job_ratings jr ON jr.shift_id=s.id WHERE s.job_type='ondemand' AND ${where} ORDER BY s.id DESC`).all(...(req.user.role==='admin'?[]:[req.user.id]));if(req.user.role==='worker')return res.json({jobs:rows.map(({rate,job_payment_id,job_amount,job_fee,job_payment_status,rating_id,rating,feedback,...safe})=>safe)});res.json({jobs:rows});}));

router.post('/jobs/:id/request',requireRole('worker'),wrap((req,res)=>{const id=parseId(req.params.id);const w=db.prepare("SELECT w.available,w.kyc_status,u.status FROM workers w JOIN users u ON u.id=w.user_id WHERE w.user_id=?").get(req.user.id);if(!w?.available||w.status!=='Active')throw conflict('Set availability before accepting work.');if(w.kyc_status!=='Verified')throw forbidden('Worker verification is required.');const out=tx(()=>{const s=job(id);if(!s)throw notFound('Job not found');if(s.status!=='Open')throw conflict('This job is no longer available.');if(db.prepare("SELECT 1 FROM applications a JOIN shifts s ON s.id=a.shift_id WHERE a.worker_id=? AND a.status='Accepted' AND s.job_type='ondemand' AND s.status IN ('Filled','Ongoing')").get(req.user.id))throw conflict('You already have an assigned job.');const app=db.prepare("INSERT INTO applications(shift_id,worker_id,status) VALUES(?,?,'Accepted')").run(id,req.user.id);const changed=db.prepare("UPDATE shifts SET status='Filled' WHERE id=? AND status='Open'").run(id);if(!changed.changes)throw conflict('This job is no longer available.');issueCodes(id);db.prepare('UPDATE workers SET available=0 WHERE user_id=?').run(req.user.id);notify(s.business_id,`${req.user.name} accepted your nearby job ${s.title}. Ask the worker for the start code when they arrive.`);return {application_id:Number(app.lastInsertRowid)};})();audit(req,'ondemand.worker_accept','shift',id);res.status(201).json({ok:true,application_id:out.application_id});}));
router.get('/jobs/:id/codes',requireRole('worker'),wrap((req,res)=>{const id=parseId(req.params.id),s=job(id);if(!s)throw notFound('Job not found');if(!assignedWorker(id,req.user.id))throw forbidden();if(!['Filled','Ongoing'].includes(s.status))throw conflict('Codes are only available for active jobs.');tx(()=>{if(!db.prepare("SELECT 1 FROM job_verifications WHERE shift_id=? AND purpose='start'").get(id)){if(s.status==='Filled')issueCodes(id);else{putCode(id,'start',newCode());db.prepare("UPDATE job_verifications SET consumed_at=datetime('now'),code_ciphertext=NULL WHERE shift_id=? AND purpose='start'").run(id);}}if(!db.prepare("SELECT 1 FROM job_verifications WHERE shift_id=? AND purpose='finish'").get(id))putCode(id,'finish',newCode());})();const get=p=>{const v=db.prepare("SELECT code_ciphertext,consumed_at FROM job_verifications WHERE shift_id=? AND purpose=?").get(id,p);return {code:v&&v.code_ciphertext&&!v.consumed_at?decrypt(id,v.code_ciphertext):null,used:Boolean(v?.consumed_at)};};res.json({status:s.status,start:get('start'),finish:get('finish')});}));
router.post('/jobs/:id/codes/regenerate',requireRole('worker'),wrap((req,res)=>{const id=parseId(req.params.id),s=job(id);if(!s)throw notFound('Job not found');if(!assignedWorker(id,req.user.id))throw forbidden();if(!['Filled','Ongoing'].includes(s.status))throw conflict('Codes are only available for active jobs.');tx(()=>{if(s.status==='Filled')issueCodes(id);else putCode(id,'finish',newCode());})();audit(req,'ondemand.codes_regenerated','shift',id);res.json({ok:true});}));
router.post('/jobs/:id/verify-start',requireRole('business'),wrap((req,res)=>{const id=parseId(req.params.id),{otp}=otpBody.parse(req.body);let invalid=false;tx(()=>{const s=job(id);if(!s)throw notFound('Job not found');if(s.business_id!==req.user.id)throw forbidden();if(s.status!=='Filled')throw conflict('This job is not waiting to be started.');const r=checkCode(id,'start',otp);if(r.invalid){invalid=true;return;}db.prepare("UPDATE shifts SET otp_verified_at=datetime('now'),status='Ongoing' WHERE id=? AND status='Filled'").run(id);const w=db.prepare("SELECT worker_id FROM applications WHERE shift_id=? AND status='Accepted'").get(id);if(w){ensureJobPayment(s,w.worker_id);notify(w.worker_id,`Shift started for ${s.title}. The customer will pay now, then enter your finish code.`);}})();if(invalid)throw bad('Start code is incorrect.');audit(req,'ondemand.start_verified','shift',id);res.json({ok:true,status:'Ongoing'});}));
router.post('/jobs/:id/verify-finish',requireRole('business'),wrap((req,res)=>{const id=parseId(req.params.id),{otp}=otpBody.parse(req.body);let invalid=false,result=null;tx(()=>{const s=db.prepare("SELECT s.*,a.worker_id FROM shifts s JOIN applications a ON a.shift_id=s.id AND a.status='Accepted' WHERE s.id=? AND s.job_type='ondemand'").get(id);if(!s)throw notFound('Job not found');if(s.business_id!==req.user.id)throw forbidden();if(s.status!=='Ongoing')throw conflict('This job has not been started.');ensureJobPayment(s,s.worker_id);const pay=db.prepare('SELECT * FROM job_payments WHERE shift_id=?').get(id);if(pay.status!=='paid')throw conflict(`Please pay ₹${pay.amount} before finishing the shift.`);const r=checkCode(id,'finish',otp);if(r.invalid){invalid=true;return;}db.prepare("UPDATE shifts SET status='Completed',completion_requested_at=datetime('now') WHERE id=? AND status='Ongoing'").run(id);db.prepare('UPDATE workers SET available=0 WHERE user_id=?').run(s.worker_id);db.prepare('DELETE FROM job_locations WHERE shift_id=?').run(id);notify(s.worker_id,'Shift finished. Thank you!');result={amount:pay.amount,fee:pay.fee};})();if(invalid)throw bad('Finish code is incorrect.');audit(req,'ondemand.finish_verified','shift',id);res.json({ok:true,status:'Completed',...result});}));
router.post('/jobs/:id/location',requireRole('worker'),wrap((req,res)=>{const id=parseId(req.params.id),p=point.extend({accuracy_m:z.coerce.number().min(0).max(10000).optional()}).parse(req.body),s=job(id);if(!s)throw notFound('Job not found');if(s.status!=='Ongoing'||!db.prepare("SELECT 1 FROM applications WHERE shift_id=? AND worker_id=? AND status='Accepted'").get(id,req.user.id))throw forbidden();db.prepare("INSERT INTO job_locations(shift_id,lat,lng,accuracy_m) VALUES(?,?,?,?) ON CONFLICT(shift_id) DO UPDATE SET lat=excluded.lat,lng=excluded.lng,accuracy_m=excluded.accuracy_m,updated_at=datetime('now')").run(id,p.lat,p.lng,p.accuracy_m??null);res.json({ok:true});}));
router.get('/jobs/:id/location',requireRole('business','worker','admin'),wrap((req,res)=>{const id=parseId(req.params.id),s=db.prepare("SELECT s.*,a.worker_id FROM shifts s LEFT JOIN applications a ON a.shift_id=s.id AND a.status='Accepted' WHERE s.id=? AND s.job_type='ondemand'").get(id);if(!s)throw notFound('Job not found');if(req.user.role==='business'&&s.business_id!==req.user.id||req.user.role==='worker'&&s.worker_id!==req.user.id)throw forbidden();if(s.status!=='Ongoing')throw conflict('Tracking is available during active work only.');const location=db.prepare('SELECT lat,lng,accuracy_m,updated_at FROM job_locations WHERE shift_id=?').get(id);res.json({available:Boolean(location),location:location||null});}));
router.post('/jobs/:id/ratings',requireRole('business'),wrap((req,res)=>{const id=parseId(req.params.id),d=z.object({rating:z.number().int().min(1).max(5),feedback:z.string().trim().max(1000).optional().default('')}).parse(req.body);tx(()=>{const s=db.prepare("SELECT s.*,a.worker_id FROM shifts s JOIN applications a ON a.shift_id=s.id AND a.status='Accepted' WHERE s.id=? AND s.job_type='ondemand'").get(id);if(!s)throw notFound();if(s.business_id!==req.user.id)throw forbidden();if(s.status!=='Completed')throw conflict('Confirm completion before rating.');if(db.prepare('SELECT 1 FROM job_ratings WHERE shift_id=?').get(id))throw conflict('Feedback has already been submitted.');db.prepare('INSERT INTO job_ratings(shift_id,business_id,worker_id,rating,feedback) VALUES(?,?,?,?,?)').run(id,req.user.id,s.worker_id,d.rating,d.feedback);db.prepare('UPDATE workers SET rating=(SELECT AVG(rating) FROM job_ratings WHERE worker_id=?) WHERE user_id=?').run(s.worker_id,s.worker_id);notify(s.worker_id,`You received a ${d.rating}-star rating.`);})();res.status(201).json({ok:true});}));
router.get('/jobs/:id/verification',requireRole('business','admin'),wrap((req,res)=>{const id=parseId(req.params.id),s=job(id);if(!s)throw notFound();if(req.user.role==='business'&&s.business_id!==req.user.id)throw forbidden();res.json({job_id:id,status:s.status,started:Boolean(s.otp_verified_at),completion_requested:Boolean(s.completion_requested_at)});}));

// Scheduled-shift customer verification. These endpoints reuse the same
// encrypted one-time codes and payment records as on-demand jobs.
function anyShift(id) {
  return db.prepare("SELECT * FROM shifts WHERE id=? AND job_type!='ondemand'").get(id);
}
function assignedWorkerRow(id) {
  return db.prepare(`SELECT a.worker_id,u.name AS worker_name
    FROM applications a JOIN users u ON u.id=a.worker_id
    WHERE a.shift_id=? AND a.status='Accepted'`).get(id);
}
router.get('/shifts/:id/workflow', requireRole('business','admin'), wrap((req,res)=>{
  const id=parseId(req.params.id), s=anyShift(id);
  if(!s) throw notFound('Scheduled shift not found');
  if(req.user.role==='business' && s.business_id!==req.user.id) throw forbidden();
  const worker=assignedWorkerRow(id);
  const startRow=db.prepare("SELECT consumed_at FROM job_verifications WHERE shift_id=? AND purpose='start'").get(id);
  const payment=db.prepare('SELECT amount,fee,status FROM job_payments WHERE shift_id=?').get(id) || null;
  res.json({
    id, status:s.status, worker_id:worker?.worker_id ?? null,
    worker_name:worker?.worker_name ?? null,
    start_verified:Boolean(startRow?.consumed_at),
    amount:payment?.amount ?? null, payment_status:payment?.status ?? 'unpaid'
  });
}));
router.get('/shifts/:id/codes', requireRole('worker'), wrap((req,res)=>{
  const id=parseId(req.params.id),s=anyShift(id);
  if(!s) throw notFound('Scheduled shift not found');
  if(!assignedWorker(id,req.user.id)) throw forbidden();
  if(!['Filled','Ongoing'].includes(s.status)) throw conflict('Codes are only available for active assigned shifts.');
  tx(()=>{
    if(!db.prepare("SELECT 1 FROM job_verifications WHERE shift_id=? AND purpose='start'").get(id)) issueCodes(id);
    if(!db.prepare("SELECT 1 FROM job_verifications WHERE shift_id=? AND purpose='finish'").get(id)) putCode(id,'finish',newCode());
  })();
  const get=purpose=>{const v=db.prepare("SELECT code_ciphertext,consumed_at FROM job_verifications WHERE shift_id=? AND purpose=?").get(id,purpose);return {code:v&&v.code_ciphertext&&!v.consumed_at?decrypt(id,v.code_ciphertext):null,used:Boolean(v?.consumed_at)};};
  res.json({status:s.status,start:get('start'),finish:get('finish')});
}));
router.post('/shifts/:id/codes/regenerate', requireRole('worker'), wrap((req,res)=>{
  const id=parseId(req.params.id),s=anyShift(id);
  if(!s) throw notFound('Scheduled shift not found');
  if(!assignedWorker(id,req.user.id)) throw forbidden();
  if(!['Filled','Ongoing'].includes(s.status)) throw conflict('Codes are only available for active assigned shifts.');
  tx(()=>{if(s.status==='Filled') issueCodes(id); else putCode(id,'finish',newCode());})();
  audit(req,'scheduled.codes_regenerated','shift',id);
  res.json({ok:true});
}));
router.post('/shifts/:id/verify-start', requireRole('business'), wrap((req,res)=>{
  const id=parseId(req.params.id),{otp}=otpBody.parse(req.body);
  let invalid=false;
  tx(()=>{
    const s=anyShift(id);
    if(!s) throw notFound('Scheduled shift not found');
    if(s.business_id!==req.user.id) throw forbidden();
    if(!['Filled','Ongoing'].includes(s.status)) throw conflict('This shift is not waiting to be started.');
    const check=checkCode(id,'start',otp);
    if(check.invalid){invalid=true;return;}
    const worker=assignedWorkerRow(id);
    if(!worker) throw conflict('No worker is assigned to this shift.');
    db.prepare("UPDATE shifts SET otp_verified_at=datetime('now'),status='Ongoing' WHERE id=?").run(id);
    ensureJobPayment(s,worker.worker_id);
    notify(worker.worker_id,`Start code verified for ${s.title}. The customer will pay before entering your finish code.`);
  })();
  if(invalid) throw bad('Start code is incorrect.');
  audit(req,'scheduled.start_verified','shift',id);
  res.json({ok:true,status:'Ongoing'});
}));
router.post('/shifts/:id/verify-finish', requireRole('business'), wrap((req,res)=>{
  const id=parseId(req.params.id),{otp}=otpBody.parse(req.body);
  let invalid=false;
  tx(()=>{
    const s=anyShift(id);
    if(!s) throw notFound('Scheduled shift not found');
    if(s.business_id!==req.user.id) throw forbidden();
    if(s.status!=='Ongoing') throw conflict('This shift has not been started.');
    const worker=assignedWorkerRow(id);
    if(!worker) throw conflict('No assigned worker found.');
    ensureJobPayment(s,worker.worker_id);
    const payment=db.prepare('SELECT * FROM job_payments WHERE shift_id=?').get(id);
    if(payment.status!=='paid') throw conflict(`Please pay ₹${payment.amount} before finishing the shift.`);
    const check=checkCode(id,'finish',otp);
    if(check.invalid){invalid=true;return;}
    db.prepare("UPDATE shifts SET status='Completed',completion_requested_at=datetime('now') WHERE id=? AND status='Ongoing'").run(id);
    notify(worker.worker_id,'Your scheduled shift was completed and verified.');
  })();
  if(invalid) throw bad('Finish code is incorrect.');
  audit(req,'scheduled.finish_verified','shift',id);
  res.json({ok:true,status:'Completed'});
}));

