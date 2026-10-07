# Notes API: login + text CRUD backend (sample project)

A small REST backend of the kind a mobile app needs: users register and log in, then create, read, update and delete their own text notes. Built by Prosync Solutions as a portfolio demo.

**Stack:** Python, Flask, SQLite, JWT bearer tokens, salted password hashes.

## Run it

```bash
pip install -r requirements.txt
python app.py                         # http://localhost:5000
python -m unittest test_api.py -v     # 7 end-to-end tests
```

Set `JWT_SECRET` in the environment before deploying.

## Endpoints

| Method | Path | Auth | What it does |
|---|---|---|---|
| POST | `/api/auth/register` | none | Create account, returns token |
| POST | `/api/auth/login` | none | Returns token |
| GET | `/api/me` | token | Current user |
| GET | `/api/notes?q=&page=&limit=` | token | List own notes, with search and paging |
| POST | `/api/notes` | token | Create a note |
| GET | `/api/notes/{id}` | token | Read one note |
| PUT / PATCH | `/api/notes/{id}` | token | Update title and/or body |
| DELETE | `/api/notes/{id}` | token | Delete a note |

Send the token as `Authorization: Bearer <token>`.

## Example

```bash
curl -X POST localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ann@example.com","password":"correct-horse"}'

curl -X POST localhost:5000/api/notes \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"title":"Shopping","body":"milk, eggs"}'
```

```json
{"id": 1, "title": "Shopping", "body": "milk, eggs",
 "created_at": "2026-10-05T10:40:00+00:00", "updated_at": "2026-10-05T10:40:00+00:00"}
```

## What it handles

- Passwords are stored only as salted hashes
- Tokens expire after 12 hours
- Every note query is scoped to the logged-in user, so one user can never read or change another's notes (tested)
- Input validation with field-level error messages (HTTP 422)
- Consistent JSON errors: 401, 404, 405, 409, 422
- Login gives the same message for a wrong email and a wrong password
