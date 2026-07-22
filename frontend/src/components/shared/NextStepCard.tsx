"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import type { ElementType } from "react";

interface NextStepCardProps {
  title: string;
  description: string;
  href: string;
  actionLabel: string;
  icon?: ElementType;
}

export function NextStepCard({ title, description, href, actionLabel, icon: Icon }: NextStepCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass-card-hover p-6 border border-border/50 bg-accent-sky/5 shadow-[0_0_20px_rgba(14,165,233,0.05)] mt-8"
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          {Icon && (
            <div className="w-12 h-12 rounded-xl bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center text-accent-sky flex-shrink-0" aria-hidden="true">
              <Icon className="w-6 h-6" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h4 className="font-heading font-semibold text-text-primary text-base mb-1">
              {title}
            </h4>
            <p className="text-text-muted text-sm max-w-xl leading-relaxed">
              {description}
            </p>
          </div>
        </div>
        <Link
          href={href}
          className="btn-primary flex items-center justify-center gap-2 whitespace-nowrap self-start md:self-center group"
        >
          <span>{actionLabel}</span>
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" aria-hidden="true" />
        </Link>
      </div>
    </motion.div>
  );
}
