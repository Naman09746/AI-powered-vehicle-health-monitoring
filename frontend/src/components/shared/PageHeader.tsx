"use client";

import { motion } from "framer-motion";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between mb-8"
    >
      <div>
        <h1 className="text-2xl font-heading font-bold text-text-primary">{title}</h1>
        {description && (
          <p className="text-text-muted text-sm mt-1">{description}</p>
        )}
      </div>
      {actions && (
        <nav className="flex items-center gap-3" aria-label="Page actions">
          {actions}
        </nav>
      )}
    </motion.div>
  );
}
