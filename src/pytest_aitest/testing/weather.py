"""Weather store for testing - mock weather data.

Provides realistic weather data for testing natural language → tool usage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pytest_aitest.testing.store import ToolResult

# Mock weather data for major cities
WEATHER_DATA = {
    "paris": {
        "city": "Paris",
        "country": "France",
        "temperature_celsius": 18,
        "temperature_fahrenheit": 64,
        "humidity": 65,
        "conditions": "Partly cloudy",
        "wind_speed_kmh": 12,
        "wind_direction": "SW",
    },
    "tokyo": {
        "city": "Tokyo",
        "country": "Japan",
        "temperature_celsius": 24,
        "temperature_fahrenheit": 75,
        "humidity": 70,
        "conditions": "Sunny",
        "wind_speed_kmh": 8,
        "wind_direction": "E",
    },
    "new york": {
        "city": "New York",
        "country": "USA",
        "temperature_celsius": 22,
        "temperature_fahrenheit": 72,
        "humidity": 55,
        "conditions": "Clear",
        "wind_speed_kmh": 15,
        "wind_direction": "NW",
    },
    "berlin": {
        "city": "Berlin",
        "country": "Germany",
        "temperature_celsius": 16,
        "temperature_fahrenheit": 61,
        "humidity": 72,
        "conditions": "Overcast",
        "wind_speed_kmh": 10,
        "wind_direction": "N",
    },
    "london": {
        "city": "London",
        "country": "UK",
        "temperature_celsius": 14,
        "temperature_fahrenheit": 57,
        "humidity": 80,
        "conditions": "Rainy",
        "wind_speed_kmh": 18,
        "wind_direction": "W",
    },
    "sydney": {
        "city": "Sydney",
        "country": "Australia",
        "temperature_celsius": 26,
        "temperature_fahrenheit": 79,
        "humidity": 60,
        "conditions": "Sunny",
        "wind_speed_kmh": 20,
        "wind_direction": "SE",
    },
}


@dataclass
class WeatherStore:
    """In-memory weather data store for testing."""

    def get_weather(self, city: str) -> ToolResult:
        """Get current weather for a city.

        Args:
            city: City name (case-insensitive)

        Returns:
            ToolResult with weather data
        """
        key = city.lower().strip()
        if key not in WEATHER_DATA:
            available = ", ".join(d["city"] for d in WEATHER_DATA.values())
            return ToolResult(
                success=False,
                value=None,
                error=f"City '{city}' not found. Available cities: {available}",
            )
        return ToolResult(success=True, value=WEATHER_DATA[key].copy())

    def get_forecast(self, city: str, days: int = 5) -> ToolResult:
        """Get weather forecast for a city.

        Args:
            city: City name (case-insensitive)
            days: Number of days to forecast (1-7)

        Returns:
            ToolResult with list of daily forecasts
        """
        if days < 1 or days > 7:
            return ToolResult(
                success=False,
                value=None,
                error="Forecast days must be between 1 and 7",
            )

        key = city.lower().strip()
        if key not in WEATHER_DATA:
            available = ", ".join(d["city"] for d in WEATHER_DATA.values())
            return ToolResult(
                success=False,
                value=None,
                error=f"City '{city}' not found. Available cities: {available}",
            )

        base = WEATHER_DATA[key]
        conditions_cycle = ["Sunny", "Partly cloudy", "Cloudy", "Rainy", "Clear"]

        forecast = []
        for i in range(days):
            temp_variation = (i % 3) - 1
            forecast.append(
                {
                    "day": i + 1,
                    "city": base["city"],
                    "high_celsius": base["temperature_celsius"] + 3 + temp_variation,
                    "low_celsius": base["temperature_celsius"] - 5 + temp_variation,
                    "conditions": conditions_cycle[i % len(conditions_cycle)],
                    "precipitation_chance": (i * 10 + 20) % 100,
                }
            )
        return ToolResult(success=True, value=forecast)

    def list_cities(self) -> ToolResult:
        """List all available cities.

        Returns:
            ToolResult with list of city names
        """
        return ToolResult(success=True, value=[d["city"] for d in WEATHER_DATA.values()])

    def compare_weather(self, city1: str, city2: str) -> ToolResult:
        """Compare weather between two cities.

        Args:
            city1: First city name
            city2: Second city name

        Returns:
            ToolResult with comparison data
        """
        result1 = self.get_weather(city1)
        if not result1.success:
            return result1

        result2 = self.get_weather(city2)
        if not result2.success:
            return result2

        weather1 = result1.value
        weather2 = result2.value

        temp_diff = weather1["temperature_celsius"] - weather2["temperature_celsius"]
        warmer = weather1["city"] if temp_diff > 0 else weather2["city"]

        return ToolResult(
            success=True,
            value={
                "city1": weather1,
                "city2": weather2,
                "temperature_difference_celsius": abs(temp_diff),
                "warmer_city": warmer if temp_diff != 0 else "same",
                "humidity_difference": abs(weather1["humidity"] - weather2["humidity"]),
            },
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call by name."""
        tools = {
            "get_weather": lambda args: self.get_weather(args["city"]),
            "get_forecast": lambda args: self.get_forecast(args["city"], args.get("days", 5)),
            "list_cities": lambda _: self.list_cities(),
            "compare_weather": lambda args: self.compare_weather(args["city1"], args["city2"]),
        }

        if name not in tools:
            return ToolResult(success=False, value=None, error=f"Unknown tool: {name}")

        try:
            return tools[name](arguments)
        except KeyError as e:
            return ToolResult(success=False, value=None, error=f"Missing argument: {e}")
        except Exception as e:
            return ToolResult(success=False, value=None, error=str(e))

    async def call_tool_async(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Async dispatch (all tools are sync for weather)."""
        return self.call_tool(name, arguments)

    @classmethod
    def get_tool_schemas(cls) -> list[dict[str, Any]]:
        """Return JSON schemas for all tools (for MCP)."""
        return [
            {
                "name": "get_weather",
                "description": "Get the current weather for a city. Returns temperature, humidity, conditions, and wind information.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name (e.g., 'Paris', 'Tokyo', 'New York')",
                        }
                    },
                    "required": ["city"],
                },
            },
            {
                "name": "get_forecast",
                "description": "Get a multi-day weather forecast for a city.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to forecast (1-7, default 5)",
                            "minimum": 1,
                            "maximum": 7,
                        },
                    },
                    "required": ["city"],
                },
            },
            {
                "name": "list_cities",
                "description": "List all cities with available weather data.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "compare_weather",
                "description": "Compare the current weather between two cities.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city1": {
                            "type": "string",
                            "description": "First city to compare",
                        },
                        "city2": {
                            "type": "string",
                            "description": "Second city to compare",
                        },
                    },
                    "required": ["city1", "city2"],
                },
            },
        ]
