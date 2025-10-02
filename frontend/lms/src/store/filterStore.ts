// store/createFilterStore.ts
import { create } from "zustand";
import type { SecurityEventFilters, UserFilters } from "../types/types";
import { createJSONStorage, persist } from "zustand/middleware";

type FilterState<T> = {
  filterValues: T;
  updateFilter: <K extends keyof T>(filterType: K, value: T[K]) => void;
  removeFilters: () => void;
};

export function createFilterStore<T extends object>(initialFilters: T) {
  return create<FilterState<T>>()(
    persist(
      (set) => ({
        filterValues: initialFilters,
        updateFilter: (filterType, value) =>
          set((state) => ({
            filterValues: { ...state.filterValues, [filterType]: value },
          })),
        removeFilters: () => set({ filterValues: initialFilters }),
      }),
      {
        name: "filter-store", // localStorage key
        storage: createJSONStorage(() => sessionStorage),
      }
    )
  );
}

export const useUserFilterStore = createFilterStore<UserFilters>({
  role: null,
  status: null,
  date: "",
  search: "",
  tenant: "",
});
export const useSecurityEventFilterStore =
  createFilterStore<SecurityEventFilters>({
    date: "",
    search: "",
    severity: null,
    eventType: null,
    tenant: null,
  });
