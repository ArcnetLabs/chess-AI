import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { User } from '@/types';

export function useCurrentUser() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const query = useQuery({
    queryKey: ['me'],
    queryFn: () => api.users.me(),
  });

  useEffect(() => {
    if (!router.isReady) return;

    if (query.data) {
      if (!query.data.chesscom_username) {
        router.replace('/onboarding/link-chesscom');
        return;
      }
      setUser(query.data);
      setLoading(false);
    } else if (query.error) {
      toast.error('Failed to load your profile.');
      setLoading(false);
    } else if (!query.isLoading && !query.data) {
      setLoading(false);
    }
  }, [query.data, query.error, query.isLoading, router]);

  return {
    user,
    userData: query.data,
    loading,
    refetchUser: query.refetch,
  };
}
