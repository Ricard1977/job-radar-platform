"""Persistent Work Order queue helpers for Job Radar."""
import uuid
from datetime import datetime, timezone, timedelta
from db.database import DB_PATH, connect, initialize

def now():
    return datetime.now(timezone.utc).isoformat()

def ensure_schema():
    initialize(DB_PATH)

def create_evaluation_order(model_version, limit=None, priority=100):
    ensure_schema()
    ts=now(); public_id=f"WO-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    with connect(DB_PATH) as conn:
        sql="""SELECT j.id FROM jobs j
               WHERE NOT EXISTS (SELECT 1 FROM ai_evaluations a WHERE a.job_id=j.id AND a.model_version=?)
               AND NOT EXISTS (
                 SELECT 1 FROM work_order_items wi JOIN work_orders wo ON wo.id=wi.work_order_id
                 WHERE wi.job_id=j.id AND wo.work_type='AI_EVALUATION' AND wo.model_version=?
                   AND wi.status IN ('PENDING','PROCESSING','RETRY_WAIT')
               )
               ORDER BY j.id DESC"""
        params=[model_version,model_version]
        if limit:
            sql+=" LIMIT ?"; params.append(limit)
        jobs=conn.execute(sql,params).fetchall()
        if not jobs: return None
        cur=conn.execute("""INSERT INTO work_orders(public_id,work_type,status,priority,model_version,total_items,created_at,updated_at)
                            VALUES(?,?,?,?,?,?,?,?)""",(public_id,'AI_EVALUATION','PENDING',priority,model_version,len(jobs),ts,ts))
        order_id=cur.lastrowid
        conn.executemany("""INSERT INTO work_order_items(work_order_id,job_id,status,priority,created_at,updated_at)
                            VALUES(?,?,'PENDING',?,?,?)""",[(order_id,r['id'],priority,ts,ts) for r in jobs])
    return public_id

def recover_stale_processing(model_version, stale_minutes=20):
    ensure_schema()
    ts=now(); cutoff=(datetime.now(timezone.utc)-timedelta(minutes=stale_minutes)).isoformat()
    with connect(DB_PATH) as conn:
        cur=conn.execute("""UPDATE work_order_items SET status='PENDING',updated_at=?,last_error='Recovered after interrupted worker'
                            WHERE status='PROCESSING' AND updated_at<? AND work_order_id IN
                            (SELECT id FROM work_orders WHERE work_type='AI_EVALUATION' AND model_version=?)""",(ts,cutoff,model_version))
        return cur.rowcount

def claim_next(model_version):
    ensure_schema(); ts=now()
    with connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("""SELECT wi.id,wi.work_order_id,wi.job_id,wi.attempts
                            FROM work_order_items wi JOIN work_orders wo ON wo.id=wi.work_order_id
                            WHERE wo.work_type='AI_EVALUATION' AND wo.model_version=?
                              AND wo.status IN ('PENDING','PROCESSING')
                              AND (wi.status='PENDING' OR (wi.status='RETRY_WAIT' AND (wi.next_attempt_at IS NULL OR wi.next_attempt_at<=?)))
                            ORDER BY wi.priority ASC,wi.id ASC LIMIT 1""",(model_version,ts)).fetchone()
        if not row: return None
        conn.execute("""UPDATE work_order_items SET status='PROCESSING',attempts=attempts+1,started_at=COALESCE(started_at,?),updated_at=? WHERE id=?""",(ts,ts,row['id']))
        conn.execute("""UPDATE work_orders SET status='PROCESSING',started_at=COALESCE(started_at,?),updated_at=? WHERE id=?""",(ts,ts,row['work_order_id']))
        return dict(row)

def mark_completed(item_id):
    ts=now()
    with connect(DB_PATH) as conn:
        conn.execute("UPDATE work_order_items SET status='COMPLETED',finished_at=?,updated_at=?,last_error=NULL,last_http_status=NULL,next_attempt_at=NULL WHERE id=?",(ts,ts,item_id))
        refresh_order(conn,item_id,ts)

def mark_retry(item_id,error,http_status=None,delay_seconds=300):
    ts=now(); nxt=(datetime.now(timezone.utc)+timedelta(seconds=delay_seconds)).isoformat()
    with connect(DB_PATH) as conn:
        conn.execute("""UPDATE work_order_items SET status='RETRY_WAIT',last_error=?,last_http_status=?,next_attempt_at=?,updated_at=? WHERE id=?""",(str(error)[:1000],http_status,nxt,ts,item_id))
        refresh_order(conn,item_id,ts)

def mark_failed(item_id,error,http_status=None):
    ts=now()
    with connect(DB_PATH) as conn:
        conn.execute("""UPDATE work_order_items SET status='FAILED',last_error=?,last_http_status=?,finished_at=?,updated_at=? WHERE id=?""",(str(error)[:1000],http_status,ts,ts,item_id))
        refresh_order(conn,item_id,ts)

def refresh_order(conn,item_id,ts=None):
    ts=ts or now()
    order=conn.execute("SELECT work_order_id FROM work_order_items WHERE id=?",(item_id,)).fetchone()
    if not order:return
    oid=order['work_order_id']
    counts={r['status']:r['n'] for r in conn.execute("SELECT status,COUNT(*) n FROM work_order_items WHERE work_order_id=? GROUP BY status",(oid,))}
    completed=counts.get('COMPLETED',0); retry=counts.get('RETRY_WAIT',0); failed=counts.get('FAILED',0)
    active=sum(counts.get(s,0) for s in ('PENDING','PROCESSING','RETRY_WAIT'))
    status='PROCESSING'; finished=None
    if active==0:
        status='COMPLETED_WITH_ERRORS' if failed else 'COMPLETED'; finished=ts
    conn.execute("""UPDATE work_orders SET status=?,completed_items=?,retry_items=?,failed_items=?,finished_at=?,updated_at=? WHERE id=?""",
                 (status,completed,retry,failed,finished,ts,oid))

def progress(public_id):
    ensure_schema()
    with connect(DB_PATH) as conn:
        row=conn.execute("""SELECT *,CASE WHEN total_items=0 THEN 100.0 ELSE ROUND(completed_items*100.0/total_items,1) END progress_pct
                            FROM work_orders WHERE public_id=?""",(public_id,)).fetchone()
        return dict(row) if row else None
