import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AppShell } from "./components/layout/AppShell";
import { SessionProvider } from "./context/SessionContext";
import { useSession } from "./context/useSession";
import { ApiError } from "./api/client";

function ThemedToaster() {
  const { theme } = useSession();
  return <Toaster position="bottom-right" theme={theme} closeButton richColors={false} />;
}

export function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Un 4xx no mejora reintentando; un fallo de red sí puede.
            retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
            staleTime: 5000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <AppShell />
        <ThemedToaster />
      </SessionProvider>
    </QueryClientProvider>
  );
}

export default App;
