# custom_tools.py
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import streamlit as st


def get_weather_description(wmo_code: int) -> str:
    """Converts WMO weather code to a human-readable description."""
    wmo_codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        56: "Light freezing drizzle", 57: "Dense freezing drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Heavy freezing rain",
        71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    return wmo_codes.get(wmo_code, "Unknown weather condition")

def get_weather(query: str, unit: str = "fahrenheit") -> str:
    """
    Fetches the real-time weather for a city by parsing the city name
    from the query and calling the Open-Meteo API.
    """
    st.info(f"Tool Invocation: `get_weather` was selected for query: '{query}'")

    match = re.search(r"\b(?:in|for|at)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", query, re.IGNORECASE)
    if not match:
        return "I couldn't figure out which city you're asking about. Please phrase your query like 'weather in New York'."

    city = match.group(1).strip()

    try:
        geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_response = requests.get(geocoding_url)
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        if not geo_data.get("results"):
            return f"I couldn't find the location for '{city}'. Please check the spelling."

        location = geo_data["results"][0]
        latitude = location["latitude"]
        longitude = location["longitude"]
        name = location.get("name", city)
        admin1 = location.get("admin1", "")
        country = location.get("country", "")
        location_display = f"{name}, {admin1}, {country}".strip(", ").replace(" ,", ",")

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
            f"&current_weather=true&temperature_unit={unit}&timezone=auto"
        )
        weather_response = requests.get(weather_url)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        current_weather = weather_data["current_weather"]
        temp = current_weather["temperature"]
        wmo_code = current_weather["weathercode"]
        temp_unit = "°F" if unit == "fahrenheit" else "°C"
        weather_desc = get_weather_description(wmo_code)
        
        local_timezone_str = weather_data["timezone"]
        datetime_str = current_weather["time"]
        
        local_tz = ZoneInfo(local_timezone_str)
        local_datetime = datetime.fromisoformat(datetime_str).astimezone(local_tz)
        
        formatted_time = local_datetime.strftime("%A, %b %d, %Y @ %I:%M %p")

        return (f"As of **{formatted_time}** local time, the current weather in "
                f"**{location_display}** is **{temp}{temp_unit}** with **{weather_desc}**.")

    except requests.exceptions.RequestException as e:
        return f"I couldn't connect to the weather service. Error: {e}"
    except (KeyError, IndexError, ZoneInfoNotFoundError):
        return "There was an issue parsing the weather or time data from the API."


