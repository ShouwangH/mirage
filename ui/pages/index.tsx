/**
 * Root page - redirects to demo experiment.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/experiment/demo');
  }, [router]);

  return (
    <>
      <Head>
        <title>Mirage</title>
      </Head>
      <main style={{ padding: '24px', textAlign: 'center' }}>
        <p>Redirecting to demo experiment...</p>
      </main>
    </>
  );
}
