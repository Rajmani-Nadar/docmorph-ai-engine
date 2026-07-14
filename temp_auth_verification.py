import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

email = f"auth-user-{uuid.uuid4().hex[:8]}@example.com"
print('registering', email)
register_resp = client.post('/auth/register', json={'name': 'Auth User', 'email': email, 'password': 'secret123'})
print('register ->', register_resp.status_code, register_resp.text)
if register_resp.status_code != 200:
    raise SystemExit('register failed')

login_resp = client.post('/auth/login', json={'email': email, 'password': 'secret123'})
print('login ->', login_resp.status_code, login_resp.text)
if login_resp.status_code != 200:
    raise SystemExit('login failed')

access_token = login_resp.json()['access_token']
refresh_token = login_resp.json()['refresh_token']
headers = {'Authorization': f'Bearer {access_token}'}

me_resp = client.get('/auth/me', headers=headers)
print('me ->', me_resp.status_code, me_resp.text)

refresh_resp = client.post('/auth/refresh', json={'refresh_token': refresh_token})
print('refresh ->', refresh_resp.status_code, refresh_resp.text)

logout_resp = client.post('/auth/logout')
print('logout ->', logout_resp.status_code, logout_resp.text)

protected_after_logout = client.get('/auth/me', headers=headers)
print('protected after logout ->', protected_after_logout.status_code, protected_after_logout.text)

# Protected endpoints auth requirement
upload_resp = client.post('/upload', files={'file': ('test.pdf', b'%PDF-1.4\n%%EOF', 'application/pdf')})
print('upload no auth ->', upload_resp.status_code, upload_resp.text)

print('done')
