"use client";

import { motion } from "framer-motion";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-6 text-center"
      role="status"
      aria-label={title}
    >
      {icon && <div className="mb-4 text-text-muted/40" aria-hidden="true">{icon}</div>}
      <h3 className="text-lg font-heading font-semibold text-text-primary mb-1">{title}</h3>
      {description && (
        <p className="text-text-muted text-sm max-w-md mb-6">{description}</p>
      )}
      {action && action}
    </motion.div>
  );
}
