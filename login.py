import os
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp

LOGIN_URL = "https://wispbyte.com/client/login"
CONSOLE_URL = "https://wispbyte.com/client/servers/fb8b17d4/console"  # 替换成你的控制台路径

# Telegram 通知函数
async def tg_notify(message: str):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("Warning: 未设置 TG_BOT_TOKEN / TG_CHAT_ID，跳过通知")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, data={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            })
        except Exception as e:
            print(f"Warning: Telegram 消息发送失败: {e}")

async def login_and_restart_iframes(email: str, password: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-dev-shm-usage", "--disable-gpu",
            "--disable-extensions", "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled"
        ])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080},
                                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        page = await context.new_page()
        page.set_default_timeout(90000)

        try:
            print(f"[{email}] 打开登录页...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)

            # 输入账号密码
            await page.fill('input[type="email"], input[type="text"]', email)
            await page.fill('input[type="password"]', password)
            await page.click('button:has-text("Log In")')

            # 等待登录完成
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            print(f"[{email}] 登录成功")

            # 跳转到控制台
            await page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=60000)
            print(f"[{email}] 已进入控制台: {page.url}")

            # 遍历所有 iframe，尝试点击重启按钮
            frames = page.frames
            print(f"[{email}] 控制台中发现 {len(frames)} 个 iframe")

            clicked = False
            for idx, frame in enumerate(frames):
                for sel in ["button:has-text('重启')", "button:has-text('Restart')",
                            "i[class*='restart']", "svg[class*='restart']",
                            "button[class*='restart']"]:
                    try:
                        print(f"[{email}] 尝试在 iframe {idx} 点击选择器: {sel}")
                        await frame.wait_for_selector(sel, timeout=5000)
                        await frame.click(sel)
                        clicked = True
                        break
                    except Exception as e:
                        print(f"[{email}] iframe {idx} 选择器 {sel} 点击失败: {e}")
                if clicked:
                    break

            if clicked:
                await asyncio.sleep(5)
                msg = f"✅ 成功点击重启按钮\n账号: <code>{email}</code>\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                print(msg)
                await tg_notify(msg)
            else:
                msg = f"❌ 未找到可点击的重启按钮（可能选择器不同）\n账号: <code>{email}</code>"
                print(msg)
                await tg_notify(msg)

        finally:
            await context.close()
            await browser.close()

async def main():
    accounts_str = os.getenv("LOGIN_ACCOUNTS")
    if not accounts_str or ":" not in accounts_str:
        print("未配置账号，格式应为 email:password")
        return

    email, password = accounts_str.split(":", 1)
    await login_and_restart_iframes(email, password)

if __name__ == "__main__":
    print(f"[{datetime.now()}] 单账号登录并尝试点击 iframe 内重启开始运行")
    asyncio.run(main())
