import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  BookOpen,
  Brain,
  LayoutGrid,
} from 'lucide-react';

export interface ChessrunNavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Pathnames that mark this item active */
  match?: string[];
}

export const CHESSRUN_SIDEBAR_NAV: ChessrunNavItem[] = [
  {
    href: '/coach',
    label: 'Coach',
    icon: Brain,
    match: ['/coach'],
  },
  {
    href: '/dashboard',
    label: 'Analysis',
    icon: BarChart3,
    match: ['/dashboard'],
  },
  {
    href: '/patterns',
    label: 'Tactics',
    icon: LayoutGrid,
    match: ['/patterns'],
  },
  {
    href: '/training',
    label: 'Training',
    icon: BookOpen,
    match: ['/training'],
  },
];

export const CHESSRUN_MOBILE_NAV: ChessrunNavItem[] = [
  {
    href: '/coach',
    label: 'Coach',
    icon: Brain,
    match: ['/coach'],
  },
  {
    href: '/dashboard',
    label: 'Analysis',
    icon: BarChart3,
    match: ['/dashboard'],
  },
  {
    href: '/patterns',
    label: 'Tactics',
    icon: LayoutGrid,
    match: ['/patterns'],
  },
  {
    href: '/training',
    label: 'Training',
    icon: BookOpen,
    match: ['/training'],
  },
];

export function isNavActive(pathname: string, item: ChessrunNavItem): boolean {
  const paths = item.match ?? [item.href];
  return paths.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}