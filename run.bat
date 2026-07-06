@echo off
REM ============================================
REM  旅伴 - 中国旅游推荐问答系统 一键启动脚本
REM  开发环境：Python 后端 + 浏览器打开前端
REM ============================================

echo ============================================
echo  旅伴 - 中国旅游推荐问答系统
echo ============================================

cd /d "%~dp0backend"

echo [1/3] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

echo [2/3] 安装依赖...
pip install -r ..\requirements.txt -q

echo [3/3] 启动服务...
echo.
echo   后端 API: http://localhost:8000
echo   API 文档: http://localhost:8000/api/docs
echo   前端页面: http://localhost:8000/../
echo.
echo   管理员账号: admin / 123456
echo.
echo 按 Ctrl+C 停止服务
echo ============================================

start "" http://localhost:8000/../index.html

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
