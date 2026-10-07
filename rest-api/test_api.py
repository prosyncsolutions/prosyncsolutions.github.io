"""End-to-end tests for the Notes API. Run: python -m unittest test_api.py -v"""
import os, tempfile, unittest
from app import create_app


class NotesApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.client = create_app(self.tmp.name, secret="test-secret-that-is-long-enough-for-hs256").test_client()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def signup(self, email="ann@example.com", password="correct-horse"):
        r = self.client.post("/api/auth/register", json={"email": email, "password": password})
        return {"Authorization": "Bearer " + r.get_json()["token"]}

    def test_register_and_login(self):
        self.signup()
        ok = self.client.post("/api/auth/login", json={"email": "Ann@Example.com", "password": "correct-horse"})
        self.assertEqual(ok.status_code, 200)
        self.assertIn("token", ok.get_json())
        bad = self.client.post("/api/auth/login", json={"email": "ann@example.com", "password": "nope-nope"})
        self.assertEqual(bad.status_code, 401)

    def test_register_validation_and_duplicates(self):
        r = self.client.post("/api/auth/register", json={"email": "not-an-email", "password": "short"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.get_json()["fields"]), {"email", "password"})
        self.signup()
        again = self.client.post("/api/auth/register", json={"email": "ann@example.com", "password": "correct-horse"})
        self.assertEqual(again.status_code, 409)

    def test_notes_require_a_token(self):
        self.assertEqual(self.client.get("/api/notes").status_code, 401)
        self.assertEqual(self.client.get("/api/notes", headers={"Authorization": "Bearer junk"}).status_code, 401)

    def test_full_crud_cycle(self):
        h = self.signup()
        created = self.client.post("/api/notes", json={"title": "Shopping", "body": "milk, eggs"}, headers=h)
        self.assertEqual(created.status_code, 201)
        nid = created.get_json()["id"]

        self.assertEqual(self.client.get(f"/api/notes/{nid}", headers=h).get_json()["body"], "milk, eggs")

        upd = self.client.patch(f"/api/notes/{nid}", json={"body": "milk, eggs, bread"}, headers=h)
        self.assertEqual(upd.get_json()["title"], "Shopping")          # untouched field kept
        self.assertEqual(upd.get_json()["body"], "milk, eggs, bread")

        self.assertEqual(self.client.delete(f"/api/notes/{nid}", headers=h).status_code, 204)
        self.assertEqual(self.client.get(f"/api/notes/{nid}", headers=h).status_code, 404)

    def test_note_validation(self):
        h = self.signup()
        self.assertEqual(self.client.post("/api/notes", json={"body": "no title"}, headers=h).status_code, 422)
        self.assertEqual(self.client.post("/api/notes", json={"title": "x" * 121}, headers=h).status_code, 422)

    def test_users_cannot_touch_each_others_notes(self):
        ann, bob = self.signup(), self.signup("bob@example.com")
        nid = self.client.post("/api/notes", json={"title": "Ann's secret"}, headers=ann).get_json()["id"]
        self.assertEqual(self.client.get(f"/api/notes/{nid}", headers=bob).status_code, 404)
        self.assertEqual(self.client.patch(f"/api/notes/{nid}", json={"title": "hacked"}, headers=bob).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/notes/{nid}", headers=bob).status_code, 404)
        self.assertEqual(self.client.get("/api/notes", headers=bob).get_json()["total"], 0)

    def test_list_search_and_pagination(self):
        h = self.signup()
        for i in range(25):
            self.client.post("/api/notes", json={"title": f"Note {i}", "body": "invoice" if i % 5 == 0 else "misc"}, headers=h)
        page1 = self.client.get("/api/notes?limit=10", headers=h).get_json()
        self.assertEqual((len(page1["items"]), page1["total"]), (10, 25))
        page3 = self.client.get("/api/notes?limit=10&page=3", headers=h).get_json()
        self.assertEqual(len(page3["items"]), 5)
        found = self.client.get("/api/notes?q=invoice", headers=h).get_json()
        self.assertEqual(found["total"], 5)


if __name__ == "__main__":
    unittest.main()
