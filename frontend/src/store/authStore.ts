import { create } from "zustand";
import { persist } from "zustand/middleware";

interface User {
  id: number;
  username: string;
  name: string | null;
  role: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  selectedVehicleId: number | null;
  setAuth: (token: string, user: User) => void;
  setSelectedVehicle: (id: number) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      selectedVehicleId: null,

      setAuth: (token, user) => set({ token, user }),

      setSelectedVehicle: (id) => set({ selectedVehicleId: id }),

      logout: () =>
        set({ token: null, user: null, selectedVehicleId: null }),
    }),
    { name: "vh-auth" }
  )
);
