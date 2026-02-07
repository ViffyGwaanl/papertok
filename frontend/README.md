# PaperTok Frontend

基于 WikiTok 的前端（React/Vite）。已把数据源从 Wikipedia API 改为本地后端：

- 默认：`http://localhost:8000/api/papers/random?limit=20`
- 可用环境变量覆盖：`VITE_API_BASE`

## 运行

### A) 推荐：由后端托管 build 后的前端（单服务）

```bash
cd wikitok/frontend
npm install
npm run build
```

然后启动后端并访问：`http://127.0.0.1:8000/`

### B) 开发：Vite dev server

```bash
cd wikitok/frontend
cp .env.example .env.local  # 可选
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

访问：`http://127.0.0.1:5173/`
