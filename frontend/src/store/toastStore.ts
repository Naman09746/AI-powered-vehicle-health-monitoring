import { create } from "zustand";

export type ToastType = "success" | "error" | "info";
export interface Toast { id: string; message: string; type: ToastType; }

interface ToastState { toasts: Toast[]; add: (msg: string, t?: ToastType) => void; remove: (id: string) => void; }

export const useToast = create<ToastState>((set) => ({
  toasts: [],
  add: (message, type = "info") => {
    const id = Math.random().toString(36).slice(2);
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 4000);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
