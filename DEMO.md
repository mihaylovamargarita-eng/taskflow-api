# TaskFlow API Demo Script

This walkthrough gives you a clean live demo flow using `curl`.

## 0. Setup

Set your API base URL:

```bash
export BASE_URL="https://taskflow-api.dtodorov.dev"
```

If you are running locally instead:

```bash
export BASE_URL="http://localhost:8000"
```

## 1. Register Two Users

```bash
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"demo-user@example.com","password":"StrongPass123"}'
```

```bash
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"demo-admin@example.com","password":"StrongPass123"}'
```

## 2. Login and Capture Tokens

User login:

```bash
USER_LOGIN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo-user@example.com&password=StrongPass123")

echo "$USER_LOGIN"
USER_ACCESS=$(echo "$USER_LOGIN" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
USER_REFRESH=$(echo "$USER_LOGIN" | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
```

Admin login:

```bash
ADMIN_LOGIN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo-admin@example.com&password=StrongPass123")

echo "$ADMIN_LOGIN"
ADMIN_ACCESS=$(echo "$ADMIN_LOGIN" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

## 3. Authenticated Profile Check

```bash
curl -s "$BASE_URL/api/auth/me" \
  -H "Authorization: Bearer $USER_ACCESS"
```

## 4. Task CRUD Demo

Create task:

```bash
TASK_CREATE=$(curl -s -X POST "$BASE_URL/api/tasks" \
  -H "Authorization: Bearer $USER_ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"title":"   Prepare    product   launch  ","description":"Finalize plan","priority":"high","status":"todo"}')

echo "$TASK_CREATE"
TASK_ID=$(echo "$TASK_CREATE" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

List tasks:

```bash
curl -s "$BASE_URL/api/tasks?status=todo&priority=high&skip=0&limit=10" \
  -H "Authorization: Bearer $USER_ACCESS"
```

Update task:

```bash
curl -s -X PUT "$BASE_URL/api/tasks/$TASK_ID" \
  -H "Authorization: Bearer $USER_ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"status":"in_progress"}'
```

Mark as done:

```bash
curl -s -X PUT "$BASE_URL/api/tasks/$TASK_ID" \
  -H "Authorization: Bearer $USER_ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"status":"done"}'
```

Try modifying completed task (expected `409`):

```bash
curl -i -X PUT "$BASE_URL/api/tasks/$TASK_ID" \
  -H "Authorization: Bearer $USER_ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"description":"should fail"}'
```

## 5. Refresh Token Rotation Demo

```bash
REFRESH_1=$(curl -s -X POST "$BASE_URL/api/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$USER_REFRESH\"}")

echo "$REFRESH_1"
NEW_REFRESH=$(echo "$REFRESH_1" | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
```

Reuse old refresh token (expected `401` reuse detection):

```bash
curl -i -X POST "$BASE_URL/api/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$USER_REFRESH\"}"
```

## 6. Admin/RBAC Demo

List users (admin):

```bash
curl -s "$BASE_URL/api/admin/users" \
  -H "Authorization: Bearer $ADMIN_ACCESS"
```

Get platform stats:

```bash
curl -s "$BASE_URL/api/admin/stats" \
  -H "Authorization: Bearer $ADMIN_ACCESS"
```

Non-admin hitting admin endpoint (expected `403`):

```bash
curl -i "$BASE_URL/api/admin/users" \
  -H "Authorization: Bearer $USER_ACCESS"
```

## 7. Health and Metrics

```bash
curl -s "$BASE_URL/api/health/live"
curl -s "$BASE_URL/api/health/ready"
curl -s "$BASE_URL/api/metrics" | head -n 20
```

## 8. Swagger Link

Open:

```bash
echo "$BASE_URL/docs"
```
