import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { User } from '@/types';

export function useCurrentUser() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const onboardingRedirected = useRef(false);

  const query = useQuery({
    queryKey: ['me'],
    queryFn: () => api.users.me(),
    retry: false,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!router.isReady) return;

    // Only block on the initial fetch — not background refetches.
    if (query.isPending) return;

    if (query.error) {
      const status = (query.error as { response?: { status?: number } })?.response
        ?.status;
      if (status === 401) {
        toast.error(
          'Signed in, but the API rejected your session. Check backend JWT settings.',
        );
      } else if (status !== undefined) {
        toast.error('Could not load your profile from the API.');
      } else {
        toast.error(
          'Could not reach the ChessIQ API (network or CORS). Check the browser console.',
        );
      }
      setUser(null);
      setLoading(false);
      return;
    }

    if (!query.data) {
      setUser(null);
      setLoading(false);
      return;
    }

    if (!query.data.chesscom_username) {
      if (!onboardingRedirected.current) {
        onboardingRedirected.current = true;
        void router.replace('/onboarding/link-chesscom');
      }
      setLoading(false);
      return;
    }

    setUser(query.data);
    setLoading(false);
  }, [query.data, query.error, query.isPending, router.isReady, router]);

  return {
    user,
    userData: query.data,
    loading,
    profileError: query.error,
    refetchUser: query.refetch,
  };
}
