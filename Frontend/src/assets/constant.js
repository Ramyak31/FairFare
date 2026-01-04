const WEATHER_STATES = [
    {
      condition: "Sunny",
      icon: "fa-sun",
      temp: "24°C • Feels like 25°C",
      hint: "Bright & dry - any car works great.",
      recommended: "Economy",
    },
    {
      condition: "Cloudy",
      icon: "fa-cloud-sun",
      temp: "18°C • Feels like 16°C",
      hint: "Mild conditions - Comfort if you prefer smoother ride.",
      recommended: "Comfort",
    },
    {
      condition: "Rainy",
      icon: "fa-cloud-rain",
      temp: "14°C • Feels like 12°C",
      hint: "Rainy - covered, larger cars (Comfort / SUV) recommended.",
      recommended: "SUV",
    },
  ];

  const CAR_TYPES = [
    { type: "Economy", icon: "fa-car-side", base: 8 },
    { type: "Comfort", icon: "fa-car-rear", base: 12 },
    { type: "Premium", icon: "fa-taxi", base: 18 },
    { type: "SUV", icon: "fa-truck-field", base: 20 },
  ];

  export {WEATHER_STATES, CAR_TYPES};