"use client";
import { useToast } from "@/store/toastStore";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle, XCircle, Info, X } from "lucide-react";

const icons = { success: CheckCircle, error: XCircle, info: Info };
const colors = { success: "border-accent-green/30 bg-accent-green/5 text-accent-green", error: "border-accent-red/30 bg-accent-red/5 text-accent-red", info: "border-accent-sky/30 bg-accent-sky/5 text-accent-sky" };

export function ToastContainer() {
  const { toasts, remove } = useToast();
  if (!toasts.length) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm" role="log" aria-live="polite">
      <AnimatePresence>
        {toasts.map((t) => {
          const Icon = icons[t.type];
          return (
            <motion.div key={t.id} initial={{ opacity: 0, y: 20, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -10, scale: 0.95 }} className={`flex items-start gap-3 p-3 rounded-lg border backdrop-blur-xl ${colors[t.type]}`}>
              <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
              <p className="text-sm flex-1">{t.message}</p>
              <button onClick={() => remove(t.id)} className="opacity-50 hover:opacity-100" aria-label="Dismiss"><X className="w-4 h-4" /></button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
