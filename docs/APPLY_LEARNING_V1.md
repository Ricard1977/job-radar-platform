# Apply Learning V1

Permanent Inbox function.

1. User presses **🧠 Aplicar aprendizaje**.
2. Frontend calls `request_learning_reanalysis()` once; repeated clicks reuse the live request.
3. GitHub Actions polls pending requests every 5 minutes.
4. Gemini receives the current learned preferences and the remaining Inbox jobs.
5. `Me interesa` and `Aplicadas` jobs are protected.
6. Gemini uses semantic job context, not keyword matching. Ambiguous cases stay in Inbox.
7. Clear negative matches are archived through `archive_and_delete_job_ai` with `Eliminada por IA · <patrón> · <motivo>`.
8. AI archives never create human `learning_signals`.
9. Archived jobs remain traceable in `treated_jobs`.

Database migrations required: `006_ai_archive.sql` and `007_learning_reanalysis_queue.sql`.
