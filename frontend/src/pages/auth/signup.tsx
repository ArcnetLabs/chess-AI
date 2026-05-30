/**
 * /auth/signup — redirects to unified passwordless login (FR-AUTH-1).
 */

import type { GetServerSideProps } from 'next'

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: {
    destination: '/auth/login',
    permanent: false,
  },
})

export default function SignUpRedirectPage() {
  return null
}
