import '@/styles/globals.css';
import type { AppProps } from 'next/app';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { useState } from 'react';
import { Chatbot } from '@/components/chat';

export default function App({ Component, pageProps }: AppProps) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60 * 5, // 5 minutes
        retry: 1,
      },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      <Component {...pageProps} />
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#141a20',
            color: '#e7ebf3',
          },
          success: {
            style: {
              background: '#214800',
              color: '#84ff00',
            },
          },
          error: {
            style: {
              background: '#450900',
              color: '#ff7351',
            },
          },
        }}
      />
      {/* AI Chess Coaching Chatbot */}
      <Chatbot />
    </QueryClientProvider>
  );
}
