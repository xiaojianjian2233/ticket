#!/usr/bin/env bash
# 形成离线安装包: 导出镜像 + compose + 文档 → tar。在服务器或构建机执行。
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="ticket-hub-install-$(date +%Y%m%d 2>/dev/null || echo pkg)"
mkdir -p "/tmp/$OUT"
echo "导出镜像..."
docker save ticket-hub-backend:local ticket-hub-frontend:local minio/minio:latest | gzip > "/tmp/$OUT/images.tar.gz"
cp -r deploy "/tmp/$OUT/"; cp .env.example "/tmp/$OUT/" 2>/dev/null || true; cp docs/ddl.sql "/tmp/$OUT/"
cat > "/tmp/$OUT/INSTALL.md" <<EOF
# ticket-hub 离线安装
1. docker load < images.tar.gz
2. 准备 .env(参考 deploy/README + .env.example), 确保 ticket_hub 库已建+ddl.sql应用+种子(scripts/seed.py)
3. docker-compose -f deploy/docker-compose.yml up -d
4. 宿主 nginx 反代 /fpy /api /webhook /minio → 前端容器:18031, 访问 http://dl.piaozone.com:18025/fpy/
EOF
tar -czf "$OUT.tar.gz" -C /tmp "$OUT"
echo "✅ 安装包: $OUT.tar.gz"
