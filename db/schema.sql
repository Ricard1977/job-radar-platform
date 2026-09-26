PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,website TEXT,linkedin_url TEXT,logo_url TEXT,sector TEXT,location TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(name));
CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,public_id TEXT NOT NULL UNIQUE,company_id INTEGER REFERENCES companies(id),title TEXT,location TEXT,workplace_type TEXT,description TEXT,salary_text TEXT,salary_min REAL,salary_max REAL,salary_currency TEXT,salary_period TEXT,status TEXT NOT NULL DEFAULT 'NEW',status_reason TEXT,first_seen_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT NOT NULL UNIQUE,name TEXT NOT NULL,source_type TEXT,enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)));
CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY AUTOINCREMENT,public_id TEXT NOT NULL UNIQUE,source_id INTEGER NOT NULL REFERENCES sources(id),name TEXT,keywords TEXT,location TEXT,date_filter TEXT,remote_filter TEXT,enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT,public_id TEXT NOT NULL UNIQUE,search_id INTEGER REFERENCES searches(id),source_id INTEGER NOT NULL REFERENCES sources(id),started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,records_found INTEGER NOT NULL DEFAULT 0,unique_records INTEGER NOT NULL DEFAULT 0,new_jobs INTEGER NOT NULL DEFAULT 0,known_jobs INTEGER NOT NULL DEFAULT 0,detail_errors INTEGER NOT NULL DEFAULT 0,truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0,1)),processed INTEGER NOT NULL DEFAULT 0 CHECK(processed IN (0,1)),error_type TEXT,error_description TEXT,raw_file TEXT);
CREATE TABLE IF NOT EXISTS job_sources (id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL REFERENCES jobs(id),source_id INTEGER NOT NULL REFERENCES sources(id),external_job_id TEXT NOT NULL,source_url TEXT,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,seen_count INTEGER NOT NULL DEFAULT 1,active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),UNIQUE(source_id,external_job_id));
CREATE TABLE IF NOT EXISTS ai_evaluations (id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL REFERENCES jobs(id),evaluated_at TEXT NOT NULL,model_version TEXT,decision TEXT,score REAL,profile_match REAL,technical_match REAL,management_match REAL,sector_match REAL,seniority_match REAL,strengths TEXT,weaknesses TEXT,reasoning TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL REFERENCES jobs(id),status TEXT NOT NULL,application_date TEXT,channel TEXT,contact_name TEXT,contact_role TEXT,next_action TEXT,next_action_date TEXT,notes TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);

-- Independent human judgement. Kept separate from applications deliberately:
-- professional interest and the decision to apply are different signals.
CREATE TABLE IF NOT EXISTS user_job_feedback (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 job_id INTEGER NOT NULL REFERENCES jobs(id),
 interest TEXT CHECK(interest IN ('INTERESTED','DOUBTFUL','NOT_INTERESTED')),
 applied INTEGER CHECK(applied IN (0,1)),
 decision_reason TEXT,
 decision_note TEXT,
 application_date TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS job_events (id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL REFERENCES jobs(id),event_type TEXT NOT NULL,event_date TEXT NOT NULL,old_value TEXT,new_value TEXT,reason TEXT,actor TEXT,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);CREATE INDEX IF NOT EXISTS idx_job_sources_job ON job_sources(job_id);CREATE INDEX IF NOT EXISTS idx_job_sources_source ON job_sources(source_id,external_job_id);CREATE INDEX IF NOT EXISTS idx_runs_search ON runs(search_id,started_at);CREATE INDEX IF NOT EXISTS idx_ai_job ON ai_evaluations(job_id,evaluated_at);CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);CREATE INDEX IF NOT EXISTS idx_feedback_job ON user_job_feedback(job_id);CREATE INDEX IF NOT EXISTS idx_feedback_applied ON user_job_feedback(applied);CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id,event_date);
INSERT OR IGNORE INTO sources(code,name,source_type,enabled) VALUES ('linkedin','LinkedIn','job_board',1);