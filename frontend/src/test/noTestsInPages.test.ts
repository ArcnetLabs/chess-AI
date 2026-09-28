import { describe, expect, it } from 'vitest';
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Next.js turns every file under `src/pages/` into a route, so a test file placed
 * there becomes a page. That is not a warning: `next build` died with
 * "Failed to collect page data for /coach/training.test" (the test imports vitest,
 * which cannot run during a build), and because the failure is at build time it
 * silently blocked two production deploys while every local test still passed.
 *
 * Cheap to check, expensive to rediscover.
 */
function filesUnder(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      found.push(...filesUnder(full));
    } else {
      found.push(full);
    }
  }
  return found;
}

describe('page directory hygiene', () => {
  it('contains no test files, which Next.js would treat as routes', () => {
    const offenders = filesUnder(join(process.cwd(), 'src', 'pages')).filter((file) =>
      /\.(test|spec)\.(ts|tsx)$/.test(file),
    );

    expect(offenders).toEqual([]);
  });
});
