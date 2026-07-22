"use client";

import { motion } from "framer-motion";
import { getHealthColor } from "@/lib/utils";

interface HealthGaugeProps {
  score: number;
  band?: string | null;
  size?: "sm" | "md" | "lg";
}

export function HealthGauge({ score, band, size = "md" }: HealthGaugeProps) {
  const radius = size === "lg" ? 80 : size === "md" ? 60 : 40;
  const strokeWidth = size === "lg" ? 10 : 8;
  const normalizedRadius = radius - strokeWidth / 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const color = getHealthColor(score);
  const progress = Math.max(0, Math.min(100, score));

  // Animate the arc
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  const bandLabel = band ?? "Health";

  return (
    <div
      className="flex flex-col items-center relative"
      role="progressbar"
      aria-valuenow={progress}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Health score: ${score.toFixed(0)}% - ${bandLabel}`}
      tabIndex={0}
    >
      <svg
        width={radius * 2}
        height={radius * 2}
        className="transform -rotate-90"
        aria-hidden="true"
      >
        {/* Background track */}
        <circle
          cx={radius}
          cy={radius}
          r={normalizedRadius}
          fill="none"
          stroke="rgba(30, 48, 71, 0.5)"
          strokeWidth={strokeWidth}
        />
        {/* Foreground arc */}
        <motion.circle
          cx={radius}
          cy={radius}
          r={normalizedRadius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: radius * 2, height: radius * 2 }} aria-hidden="true">
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="font-heading font-bold"
          style={{ fontSize: size === "lg" ? "2rem" : "1.5rem", color }}
        >
          {score.toFixed(0)}
        </motion.span>
        <span className="text-[10px] text-text-muted tracking-wider uppercase">
          {bandLabel}
        </span>
      </div>
    </div>
  );
}
