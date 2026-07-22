"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { formatTimestamp } from "@/lib/utils";

interface SensorConfig {
  key: string;
  label: string;
  unit: string;
  min: number;
  max: number;
}

const sensorConfigs: Record<string, SensorConfig> = {
  engine_temp: { key: "engine_temp", label: "Engine Temperature", unit: "°C", min: 75, max: 105 },
  oil_pressure: { key: "oil_pressure", label: "Oil Pressure", unit: "psi", min: 25, max: 65 },
  coolant_temp: { key: "coolant_temp", label: "Coolant Temperature", unit: "°C", min: 75, max: 105 },
  engine_rpm: { key: "engine_rpm", label: "Engine RPM", unit: "RPM", min: 600, max: 4500 },
  vibration: { key: "vibration", label: "Vibration", unit: "mm/s", min: 0, max: 3 },
  battery_voltage: { key: "battery_voltage", label: "Battery Voltage", unit: "V", min: 12.4, max: 14.7 },
  tire_pressure: { key: "tire_pressure", label: "Tire Pressure", unit: "psi", min: 30, max: 35 },
  speed: { key: "speed", label: "Speed", unit: "km/h", min: 0, max: 140 },
  engine_load: { key: "engine_load", label: "Engine Load", unit: "%", min: 10, max: 80 },
};

interface SensorTrendChartProps {
  data: Record<string, unknown>[];
  sensor: string;
}

export function SensorTrendChart({ data, sensor }: SensorTrendChartProps) {
  const config = sensorConfigs[sensor] ?? {
    key: sensor,
    label: sensor.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
    unit: "",
    min: 0,
    max: 100,
  };

  return (
    <div className="w-full h-64" role="img" aria-label={`${config.label} sensor trend chart. Normal range: ${config.min}–${config.max} ${config.unit}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30, 48, 71, 0.5)" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(v) => formatTimestamp(v)}
            stroke="#8da4c4"
            fontSize={11}
            tickLine={false}
          />
          <YAxis
            stroke="#8da4c4"
            fontSize={11}
            tickLine={false}
            domain={[config.min * 0.8, config.max * 1.2]}
            label={{ value: config.unit, angle: -90, position: "insideLeft", style: { fill: "#8da4c4", fontSize: 11 } }}
          />
          <Tooltip
            contentStyle={{
              background: "rgba(15, 25, 36, 0.95)",
              border: "1px solid rgba(30, 48, 71, 0.5)",
              borderRadius: "8px",
              backdropFilter: "blur(12px)",
            }}
            labelFormatter={(v) => formatTimestamp(v)}
          />
          <ReferenceLine y={config.max} stroke="#f59e0b" strokeDasharray="4 4" />
          <ReferenceLine y={config.min} stroke="#f59e0b" strokeDasharray="4 4" />
          <ReferenceArea y1={config.min} y2={config.max} fill="#10b981" fillOpacity={0.04} />
          <Line
            type="monotone"
            dataKey={sensor}
            stroke="#0ea5e9"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#0ea5e9" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export { sensorConfigs };
