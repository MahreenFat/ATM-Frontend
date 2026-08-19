# OOP Bank ATM — Full Stack Project

## IMPORTANT: How to run

1. Extract this ZIP.
2. Open the extracted `ATM_FullStack_Project_FIXED` folder.
3. Double-click **`run_backend.bat`**.
4. Keep the black server window open.
5. Your browser will open automatically at:
   `http://127.0.0.1:5000`
6. Login with:
   - Card: `4111111111111111`
   - PIN: `1234`

### Do NOT use
`http://127.0.0.1:5500/frontend/index.html`

The Flask backend serves the frontend itself on port 5000.

### If you still see "Cannot connect to ATM backend"
Look at the black server window. If it shows a Python/Flask error, copy that error and send it to me.

## Project structure

- `frontend/` — HTML, CSS, JavaScript UI
- `backend/app.py` — Flask API and OOP business logic
- `backend/requirements.txt` — Flask + CORS
- `database/atm.db` — SQLite database
- `run_backend.bat` — one-click Windows launcher
