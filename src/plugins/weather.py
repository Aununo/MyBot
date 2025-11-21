import httpx
import os
from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import MessageEvent, Message
from nonebot.exception import FinishedException
from nonebot.log import logger
from nonebot.params import CommandArg, ArgPlainText
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule
from nonebot.typing import T_State
from pydantic import BaseModel
from datetime import datetime
import pytz


class Config(BaseModel):
    weather_api_key: str = ""

try:
    plugin_config = Config.model_validate(dict(get_driver().config))

    API_KEY = os.getenv("WEATHER_API_KEY") or plugin_config.weather_api_key
    if not API_KEY:
        raise ValueError("WEATHER_API_KEY in .env is empty.")
except Exception as e:
    logger.warning(f"天气插件 API Key 加载失败, 请检查 .env 文件: {e}")
    API_KEY = ""


def slash_only_rule(*commands: str) -> Rule:
    async def _checker(event: MessageEvent) -> bool:
        plain_text = event.get_plaintext().lstrip()
        return any(
            plain_text.startswith(command) and (len(plain_text) == len(command) or plain_text[len(command)].isspace())
            for command in commands
        )

    return Rule(_checker)


weather = on_command(
    "weather",
    aliases={"天气"},
    priority=5,
    block=True,
    rule=slash_only_rule("/weather", "/天气"),
)

@weather.handle()
async def handle_first_receive(state: T_State, args: Message = CommandArg()):
    plain_text = args.extract_plain_text().strip()
    if plain_text:
        state["city"] = args

@weather.got("city", prompt="你想查询哪个城市的天气呢？")
async def handle_weather(event: MessageEvent, city: str = ArgPlainText("city")):
    if not API_KEY:
        await weather.finish("机器人未配置天气 API Key，请联系管理员！")

    city = city.strip()
    if not city:
        await weather.reject("城市名不能为空哦，请重新输入！")
    
    utc_tz = pytz.utc
    china_tz = pytz.timezone('Asia/Shanghai')

    try:
        async with httpx.AsyncClient() as client:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={API_KEY}"
            geo_resp = await client.get(geo_url, timeout=10.0)
            if geo_resp.status_code != 200 or not geo_resp.json():
                await weather.finish(f"哎呀，没有找到城市“{city}”的地理信息，请检查城市名是否正确。")
            
            geo_data = geo_resp.json()[0]
            lat, lon = geo_data.get('lat'), geo_data.get('lon')
            city_name = geo_data.get('local_names', {}).get('zh', geo_data.get('name'))

            weather_url = (f"https://api.openweathermap.org/data/3.0/onecall?"
                           f"lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=zh_cn&exclude=minutely")
            weather_resp = await client.get(weather_url, timeout=10.0)
            
            if weather_resp.status_code != 200:
                if weather_resp.status_code == 401:
                    logger.error("天气 API Key 无效或未订阅 One Call API，请检查配置。")
                    await weather.finish("天气服务认证失败，请联系管理员检查 API Key 或订阅。")
                else:
                    logger.error(f"请求天气 API 时发生未知 HTTP 错误: {weather_resp.status_code} - {weather_resp.text}")
                    await weather.finish("获取天气信息时遇到了一点小问题，请稍后再试。")
            
            data = weather_resp.json()
            
            reply_lines = []
            if data.get("alerts"):
                alert = data["alerts"][0]
                reply_lines.append(f"⚠️ [ {alert.get('event', '未知预警')} ]")

            current = data["current"]
            reply_lines.append(f"🏙️ {city_name} - 当前天气")
            reply_lines.append(f"└ 🌦️ {current['weather'][0]['description']} | {current['temp']}°C (体感 {current['feels_like']}°C)")
            reply_lines.append(f"└ 💧 {current['humidity']}% | 🌬️ {current['wind_speed']} m/s | ☔ {data['daily'][0]['pop'] * 100:.0f}%")
            
            reply_lines.append("\n🕒 未来几小时预报")
            hourly_forecasts = data.get("hourly", [])

            for hour_data in hourly_forecasts[1:4]:
                utc_dt = datetime.fromtimestamp(hour_data["dt"], tz=utc_tz)
                china_dt = utc_dt.astimezone(china_tz)
                time_str = china_dt.strftime("%H:%M")
                
                reply_lines.append(f"└ {time_str} - {hour_data['weather'][0]['description']}, {hour_data['temp']}°C, {hour_data['pop'] * 100:.0f}%")
            
            reply_lines.append("\n📅 未来三天天气预报")
            for day_data in data["daily"][1:4]:
                utc_dt = datetime.fromtimestamp(day_data["dt"], tz=utc_tz)
                china_dt = utc_dt.astimezone(china_tz)
                date = china_dt.strftime("%m-%d")

                reply_lines.append(f"└ {date}: {day_data['weather'][0]['description']}, {day_data['temp']['min']:.1f}~{day_data['temp']['max']:.1f}°C, {day_data['pop'] * 100:.0f}%")
            
            await weather.finish("\n".join(reply_lines))

    except FinishedException:
        raise
    except httpx.TimeoutException:
        logger.warning(f"请求天气 API 超时")
        await weather.finish("获取天气信息超时了，请稍后再试。")
    except Exception as e:
        logger.error(f"处理天气查询时发生未知错误: {e}")
        await weather.finish("处理天气查询时发生未知错误，请联系管理员。")