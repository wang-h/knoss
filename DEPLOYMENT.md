# Knoss 部署指南 / Deployment Guide

[English](#english) | [中文](#中文)

---

## 中文

### 📋 部署前准备

**系统要求:**
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- 4GB RAM 最小
- 10GB 磁盘空间

**依赖服务:**
- PostgreSQL 数据库
- (可选) Redis 缓存
- (可选) FastAPI + Uvicorn (API服务器)

---

### 🔧 后端部署

#### 1. 克隆代码

```bash
git clone https://github.com/wang-h/knoss.git
cd knoss
```

#### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

如果没有 `requirements.txt`，手动安装：

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic python-multipart python-jose[cryptography] passlib[bcrypt] alembic
```

#### 4. 配置环境变量

创建 `.env` 文件：

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/knoss_db
DATABASE_USER=your_user
DATABASE_PASSWORD=your_password
DATABASE_NAME=knoss_db
DATABASE_HOST=localhost
DATABASE_PORT=5432

# API配置
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=True
LOG_LEVEL=info

# 安全配置
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS配置
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# (可选) Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

#### 5. 初始化数据库

```bash
# 创建数据库
createdb knoss_db

# 运行迁移
alembic upgrade head

# 或初始化SQL
python -c "
from knoss.repositories.models import Base
from sqlalchemy import create_engine
engine = create_engine('postgresql://user:password@localhost:5432/knoss_db')
Base.metadata.create_all(engine)
print('数据库初始化完成')
"
```

#### 6. 启动后端服务

```bash
# 开发环境
uvicorn knoss.main:app --reload --host 0.0.0.0 --port 8000

# 生产环境
uvicorn knoss.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 7. 验证后端部署

```bash
# 检查健康状态
curl http://localhost:8000/health

# 检查API文档
open http://localhost:8000/docs
```

---

### 🌐 前端部署

#### 1. 进入前端目录

```bash
cd frontend
```

#### 2. 安装依赖

```bash
npm install
# 或
yarn install
```

#### 3. 配置环境变量

创建 `.env.production` 文件：

```bash
# API配置
VITE_API_BASE_URL=http://your-backend-url:8000
VITE_API_TIMEOUT=30000

# 应用配置
VITE_APP_NAME=Knoss
VITE_APP_VERSION=1.0.0
```

#### 4. 构建生产版本

```bash
npm run build
# 或
yarn build
```

#### 5. 启动前端服务

**开发环境:**
```bash
npm run dev
# 或
yarn dev
# 访问: http://localhost:5173
```

**生产环境 (使用Nginx):**

```bash
# 1. 构建静态文件
npm run build

# 2. 配置Nginx
sudo nano /etc/nginx/sites-available/knoss
```

Nginx配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/knoss/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端API代理
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket支持 (开发环境热重载)
    location /ws {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/knoss /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### 🐳 Docker部署 (推荐)

#### 1. 创建 Dockerfile

**后端 Dockerfile:**

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "knoss.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**前端 Dockerfile:**

```dockerfile
FROM node:18-alpine as builder

WORKDIR /app

COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

COPY frontend/ ./frontend/
RUN cd frontend && npm run build

FROM nginx:alpine

COPY --from=builder /app/frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

#### 2. 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_USER: knoss
      POSTGRES_PASSWORD: knoss_password
      POSTGRES_DB: knoss_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://knoss:knoss_password@db:5432/knoss_db
    depends_on:
      - db
    volumes:
      - ./knoss:/app/knoss

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

#### 3. 启动服务

```bash
docker-compose up -d
```

---

### 🚀 生产环境部署

#### 使用Systemd服务

**后端服务 (`/etc/systemd/system/knoss-backend.service`):**

```ini
[Unit]
Description=Knoss Backend API
After=network.target postgresql.service

[Service]
Type=notify
User=knoss
WorkingDirectory=/opt/knoss
Environment="PATH=/opt/knoss/venv/bin"
ExecStart=/opt/knoss/venv/bin/uvicorn knoss.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable knoss-backend
sudo systemctl start knoss-backend
sudo systemctl status knoss-backend
```

#### 使用PM2 (Node.js进程管理)

```bash
# 安装PM2
npm install -g pm2

# 启动前端
cd frontend
pm2 start npm --name "knoss-frontend" -- run dev

# 保存PM2配置
pm2 save
pm2 startup
```

---

### 🔍 健康检查

**后端健康检查:**

```bash
# API健康状态
curl http://localhost:8000/health

# 数据库连接
curl http://localhost:8000/api/v1/health/db

# 详细健康状态
curl http://localhost:8000/api/v1/health/detailed
```

**前端健康检查:**

```bash
# 检查前端是否运行
curl http://localhost:5173

# 检查构建文件是否存在
ls -la frontend/dist/
```

---

### 📊 监控和日志

**查看后端日志:**

```bash
# 开发环境
# 日志直接输出到终端

# 生产环境 (使用journalctl)
sudo journalctl -u knoss-backend -f

# 查看最近100行
sudo journalctl -u knoss-backend -n 100
```

**查看前端日志:**

```bash
# PM2日志
pm2 logs knoss-frontend

# Nginx日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

### 🛠️ 故障排除

**常见问题:**

1. **数据库连接失败**
   ```bash
   # 检查PostgreSQL是否运行
   sudo systemctl status postgresql
   
   # 检查数据库是否存在
   psql -U postgres -l
   
   # 检查连接
   psql -U postgres -d knoss_db
   ```

2. **端口被占用**
   ```bash
   # 查找占用端口的进程
   lsof -i :8000
   lsof -i :5173
   
   # 杀死进程
   kill -9 <PID>
   ```

3. **前端构建失败**
   ```bash
   # 清除缓存重新安装
   rm -rf node_modules package-lock.json
   npm install
   ```

4. **API跨域问题**
   - 检查后端CORS配置
   - 确保前端API地址正确

---

### 🔒 安全配置

**生产环境安全检查清单:**

- [ ] 修改默认SECRET_KEY
- [ ] 启用HTTPS (SSL证书)
- [ ] 配置防火墙
- [ ] 限制数据库访问
- [ ] 启用API rate limiting
- [ ] 配置日志轮转
- [ ] 定期备份数据库

**HTTPS配置 (Let's Encrypt):**

```bash
# 安装certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

---

### 📈 性能优化

**后端优化:**

```bash
# 使用Gunicorn (多worker)
pip install gunicorn
gunicorn knoss.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 启用Redis缓存
pip install redis
```

**前端优化:**

```bash
# 构建优化
npm run build -- --prod

# 启用CDN
# 修改vite.config.ts配置base路径
```

---

## English

### 📋 Pre-deployment Requirements

**System Requirements:**
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- 4GB RAM minimum
- 10GB disk space

**Required Services:**
- PostgreSQL database
- (Optional) Redis cache
- (Optional) FastAPI + Uvicorn (API server)

---

### 🔧 Backend Deployment

#### 1. Clone Repository

```bash
git clone https://github.com/wang-h/knoss.git
cd knoss
```

#### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If no `requirements.txt`, install manually:

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic python-multipart python-jose[cryptography] passlib[bcrypt] alembic
```

#### 4. Configure Environment Variables

Create `.env` file:

```bash
# Database configuration
DATABASE_URL=postgresql://user:password@localhost:5432/knoss_db
DATABASE_USER=your_user
DATABASE_PASSWORD=your_password
DATABASE_NAME=knoss_db
DATABASE_HOST=localhost
DATABASE_PORT=5432

# API configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=True
LOG_LEVEL=info

# Security configuration
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS configuration
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# (Optional) Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

#### 5. Initialize Database

```bash
# Create database
createdb knoss_db

# Run migrations
alembic upgrade head

# Or initialize with SQL
python -c "
from knoss.repositories.models import Base
from sqlalchemy import create_engine
engine = create_engine('postgresql://user:password@localhost:5432/knoss_db')
Base.metadata.create_all(engine)
print('Database initialized')
"
```

#### 6. Start Backend Service

```bash
# Development environment
uvicorn knoss.main:app --reload --host 0.0.0.0 --port 8000

# Production environment
uvicorn knoss.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 7. Verify Backend Deployment

```bash
# Check health status
curl http://localhost:8000/health

# Check API docs
open http://localhost:8000/docs
```

---

### 🌐 Frontend Deployment

#### 1. Enter Frontend Directory

```bash
cd frontend
```

#### 2. Install Dependencies

```bash
npm install
# or
yarn install
```

#### 3. Configure Environment Variables

Create `.env.production` file:

```bash
# API configuration
VITE_API_BASE_URL=http://your-backend-url:8000
VITE_API_TIMEOUT=30000

# Application configuration
VITE_APP_NAME=Knoss
VITE_APP_VERSION=1.0.0
```

#### 4. Build Production Version

```bash
npm run build
# or
yarn build
```

#### 5. Start Frontend Service

**Development Environment:**
```bash
npm run dev
# or
yarn dev
# Visit: http://localhost:5173
```

**Production Environment (using Nginx):**

```bash
# 1. Build static files
npm run build

# 2. Configure Nginx
sudo nano /etc/nginx/sites-available/knoss
```

Nginx configuration example:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend static files
    location / {
        root /path/to/knoss/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (dev environment hot reload)
    location /ws {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable configuration:

```bash
sudo ln -s /etc/nginx/sites-available/knoss /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### 🐳 Docker Deployment (Recommended)

#### 1. Create Dockerfile

**Backend Dockerfile:**

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "knoss.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile:**

```dockerfile
FROM node:18-alpine as builder

WORKDIR /app

COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

COPY frontend/ ./frontend/
RUN cd frontend && npm run build

FROM nginx:alpine

COPY --from=builder /app/frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

#### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_USER: knoss
      POSTGRES_PASSWORD: knoss_password
      POSTGRES_DB: knoss_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://knoss:knoss_password@db:5432/knoss_db
    depends_on:
      - db
    volumes:
      - ./knoss:/app/knoss

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

#### 3. Start Services

```bash
docker-compose up -d
```

---

### 🚀 Production Deployment

#### Using Systemd Services

**Backend service (`/etc/systemd/system/knoss-backend.service`):**

```ini
[Unit]
Description=Knoss Backend API
After=network.target postgresql.service

[Service]
Type=notify
User=knoss
WorkingDirectory=/opt/knoss
Environment="PATH=/opt/knoss/venv/bin"
ExecStart=/opt/knoss/venv/bin/uvicorn knoss.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable knoss-backend
sudo systemctl start knoss-backend
sudo systemctl status knoss-backend
```

#### Using PM2 (Node.js Process Manager)

```bash
# Install PM2
npm install -g pm2

# Start frontend
cd frontend
pm2 start npm --name "knoss-frontend" -- run dev

# Save PM2 configuration
pm2 save
pm2 startup
```

---

### 🔍 Health Checks

**Backend health check:**

```bash
# API health status
curl http://localhost:8000/health

# Database connection
curl http://localhost:8000/api/v1/health/db

# Detailed health status
curl http://localhost:8000/api/v1/health/detailed
```

**Frontend health check:**

```bash
# Check if frontend is running
curl http://localhost:5173

# Check if build files exist
ls -la frontend/dist/
```

---

### 📊 Monitoring and Logging

**View backend logs:**

```bash
# Development environment
# Logs output directly to terminal

# Production environment (using journalctl)
sudo journalctl -u knoss-backend -f

# View last 100 lines
sudo journalctl -u knoss-backend -n 100
```

**View frontend logs:**

```bash
# PM2 logs
pm2 logs knoss-frontend

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

### 🛠️ Troubleshooting

**Common Issues:**

1. **Database connection failed**
   ```bash
   # Check if PostgreSQL is running
   sudo systemctl status postgresql
   
   # Check if database exists
   psql -U postgres -l
   
   # Check connection
   psql -U postgres -d knoss_db
   ```

2. **Port already in use**
   ```bash
   # Find process using port
   lsof -i :8000
   lsof -i :5173
   
   # Kill process
   kill -9 <PID>
   ```

3. **Frontend build failed**
   ```bash
   # Clear cache and reinstall
   rm -rf node_modules package-lock.json
   npm install
   ```

4. **API CORS issues**
   - Check backend CORS configuration
   - Verify frontend API URL is correct

---

### 🔒 Security Configuration

**Production Security Checklist:**

- [ ] Change default SECRET_KEY
- [ ] Enable HTTPS (SSL certificate)
- [ ] Configure firewall
- [ ] Restrict database access
- [ ] Enable API rate limiting
- [ ] Configure log rotation
- [ ] Regular database backups

**HTTPS Configuration (Let's Encrypt):**

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

---

### 📈 Performance Optimization

**Backend optimization:**

```bash
# Use Gunicorn (multiple workers)
pip install gunicorn
gunicorn knoss.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Enable Redis cache
pip install redis
```

**Frontend optimization:**

```bash
# Build optimization
npm run build -- --prod

# Enable CDN
# Modify vite.config.ts to set base path
```
