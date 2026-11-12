#!/usr/bin/env bash
# cite-holmes 测试套件统一入口（v6.4.0 M4）——pytest 未装环境（unittest discover）
# 与 CI（--verbose 里程碑）共用一条命令；耗时上限锁防套件腐化。
# 用法:
#   tools/run_tests.sh                 # 标准档（unittest discover -v 1）
#   tools/run_tests.sh --verbose       # CI 档：逐测试名输出+里程碑计时（横向共性①）
#   tools/run_tests.sh --budget 200    # 自定义耗时预算秒（默认 200=基线 152s×1.3）
# 退出码 0=全绿且在预算内；1=有失败或超预算。
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SK="$(cd "$HERE/.." && pwd)"
VERBOSE=0; BUDGET=200
while [ $# -gt 0 ]; do
  case "$1" in
    --verbose) VERBOSE=1 ;;
    --budget) BUDGET="$2"; shift ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
  shift
done

cd "$SK" || exit 1
echo "== cite-holmes 套件（unittest discover）=="
START=$(date +%s)
if [ "$VERBOSE" -eq 1 ]; then
  python3 -m unittest discover -s tests -p "test_*.py" -v 2>&1 | \
    awk '/^test |^Ran |^OK|^FAILED/ { print strftime("[%H:%M:%S]") " " $0; fflush() } !/^test / { print }'
else
  python3 -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -4
fi
RC=${PIPESTATUS[0]}
END=$(date +%s)
ELAPSED=$((END - START))
echo "== 耗时 ${ELAPSED}s（预算 ${BUDGET}s，基线 152s）=="
if [ "$RC" -ne 0 ]; then
  echo "RESULT: FAIL（存在失败用例）"; exit 1
fi
if [ "$ELAPSED" -gt "$BUDGET" ]; then
  echo "RESULT: FAIL（超耗时预算——套件腐化信号，检查新增重负载用例）"; exit 1
fi
echo "RESULT: PASS（全绿且在预算内）"
