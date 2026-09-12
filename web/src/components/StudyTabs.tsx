"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { slug: "", label: "Overview" },
  { slug: "audience", label: "Audience" },
  { slug: "task", label: "Task" },
  { slug: "stimulus", label: "Stimulus" },
  { slug: "simulation", label: "Simulation" },
];

// Each "tab" is a distinct route, not a client-side panel switch — plain nav
// links with aria-current is the correct accessible pattern here, not the
// ARIA tablist/tab roles (those are for same-page panel toggling).
export function StudyTabs({ studyId }: { studyId: string }) {
  const pathname = usePathname();
  const base = `/studies/${studyId}`;

  return (
    <nav className="flex gap-6 border-b border-hairline">
      {TABS.map((tab) => {
        const href = tab.slug ? `${base}/${tab.slug}` : base;
        const isActive = pathname === href;
        return (
          <Link
            key={tab.slug}
            href={href}
            aria-current={isActive ? "page" : undefined}
            className={`-mb-px border-b-2 py-3 text-[14px] font-medium transition-colors ${
              isActive
                ? "border-ink text-ink"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
