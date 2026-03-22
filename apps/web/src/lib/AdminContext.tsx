import { createContext, useContext, useState, useCallback, ReactNode } from "react";

interface AdminContextValue {
  adminKey: string;
  isAdmin: boolean;
  setAdminKey: (key: string) => void;
  clearAdmin: () => void;
}

const STORAGE_KEY = "admin_key";

const AdminContext = createContext<AdminContextValue>({
  adminKey: "",
  isAdmin: false,
  setAdminKey: () => {},
  clearAdmin: () => {},
});

export function AdminProvider({ children }: { children: ReactNode }) {
  const [adminKey, setAdminKeyState] = useState(
    () => sessionStorage.getItem(STORAGE_KEY) || "",
  );

  const setAdminKey = useCallback((key: string) => {
    sessionStorage.setItem(STORAGE_KEY, key);
    setAdminKeyState(key);
  }, []);

  const clearAdmin = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setAdminKeyState("");
  }, []);

  return (
    <AdminContext.Provider value={{ adminKey, isAdmin: !!adminKey, setAdminKey, clearAdmin }}>
      {children}
    </AdminContext.Provider>
  );
}

export function useAdmin() {
  return useContext(AdminContext);
}
