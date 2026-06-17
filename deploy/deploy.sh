#!/usr/bin/env bash
# ticket-hub 部署脚本（在服务器上执行；前后端分开容器，复用共享 PG ticket_hub）
# 用法：在仓库根目录 bash deploy/deploy.sh [build|up|down|logs|seed]
set -euo pipefail
cd "$(dirname "$0")/.."
CMD="${1:-up}"
COMPOSE="docker compose -f deploy/docker-compose.yml"

case "$CMD" in
  build) $COMPOSE build ;;
  up)    $COMPOSE build && $COMPOSE up -d && $COMPOSE ps ;;
  down)  $COMPOSE down ;;
  logs)  $COMPOSE logs -f --tail=100 ;;
  seed)  $COMPOSE run --rm backend python scripts/seed.py ;;  # 9 SKILL.md→t_skill_md + 种子
  ddl)   $COMPOSE run --rm backend python -c "import asyncio,app.scripts" 2>/dev/null || echo "ddl 已在 ticket_hub 应用(见 docs/ddl.sql)";;
  *)     echo "用法: bash deploy/deploy.sh [build|up|down|logs|seed]"; exit 1 ;;
esac
echo "访问: http://dl.piaozone.com:18025/fpy/"
